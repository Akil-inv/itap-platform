"""Application service: the one place that orchestrates rule evaluation
and persistence together. Screens (Streamlit) call this, never the repo
or the RuleEngine directly.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from .clock import today
from .domain import (
    Assignment,
    AssignmentKind,
    ChangeRequest,
    ClosureRecord,
    DuplicateAssignment,
    GoalSetting,
    GoalSettingFrozen,
    RequestStatus,
    RequestType,
    ReverseFeedback,
    ReviewScore,
    ReviewScoreFrozen,
)
from .ports import AssignmentRepo
from .rules import RuleEngine, TransitionDenied
from .rules_config import default_transition_table, guard_min_elapsed


class AssignmentService:
    def __init__(self, repo: AssignmentRepo, min_days_before_closure: int = 30):
        self._repo = repo
        self._min_days_before_closure = min_days_before_closure
        self._engine = RuleEngine(default_transition_table(min_days_before_closure))

    def create_assignment(
        self,
        agent_id: UUID,
        manager_id: UUID,
        start_date: date,
        end_date: date | None = None,
        kind: AssignmentKind = AssignmentKind.PRIMARY,
    ) -> Assignment:
        # Only same Agent/Manager-pair duplication is rejected here — the
        # "exactly one active Primary" rule from the redesign spec
        # (docs/associate_journey_redesign.md) is enforced by whichever
        # UI action creates a Primary (it's the one place that knows
        # whether the caller means a rotation move or a genuine
        # Secondary); this data-model layer stays permissive so the
        # long-standing cross-team bifurcation case (same Agent, two
        # concurrent Managers) keeps working exactly as before.
        existing = self._repo.list_by_agent(agent_id)
        for a in existing:
            if a.manager_id == manager_id and a.state.value == "active":
                raise DuplicateAssignment(agent_id, manager_id)

        assignment = Assignment(
            agent_id=agent_id,
            manager_id=manager_id,
            start_date=start_date,
            end_date=end_date,
            kind=kind,
        )
        self._repo.add(assignment)
        return assignment

    def record_goal_setting(
        self, assignment_id: UUID, goals: str, criteria: list[str] | None = None
    ) -> GoalSetting:
        """Create or edit the goal text for an Assignment — an upsert, so
        the manager/associate can keep revising it up to the point it's
        frozen (docs/associate_journey_redesign.md's "Goals tab": agreed
        verbally offline, then keyed in). Raises GoalSettingFrozen if the
        existing record is already frozen — only
        AssignmentService.reopen_goal_setting (admin) can clear that."""
        self._repo.get(assignment_id)  # raises AssignmentNotFound if missing
        existing = self._repo.get_goal_setting(assignment_id)
        if existing is not None:
            if existing.frozen:
                raise GoalSettingFrozen(
                    "Goals are frozen — an admin must reopen them before they can be edited"
                )
            existing.goals = goals
            existing.criteria = criteria or []
            self._repo.update_goal_setting(existing)
            return existing
        goal_setting = GoalSetting(
            assignment_id=assignment_id, goals=goals, criteria=criteria or []
        )
        self._repo.add_goal_setting(goal_setting)
        return goal_setting

    def freeze_goal_setting(self, assignment_id: UUID, agreed_by: UUID) -> GoalSetting:
        """The manager's "Agree & Freeze" action — locks the goal text for
        both parties. Only an admin (reopen_goal_setting) can undo this."""
        goal_setting = self._repo.get_goal_setting(assignment_id)
        if goal_setting is None:
            raise ValueError("No goal setting recorded yet — nothing to freeze")
        if goal_setting.frozen:
            raise GoalSettingFrozen("Goals are already frozen")
        goal_setting.frozen = True
        goal_setting.agreed_by = agreed_by
        goal_setting.agreed_at = datetime.now(timezone.utc)
        self._repo.update_goal_setting(goal_setting)
        return goal_setting

    def reopen_goal_setting(self, assignment_id: UUID) -> GoalSetting:
        """Admin-only action (not gated here — RBAC/UI enforces who may
        call this) that clears a goal freeze so a new project can be
        added mid-engagement, per spec. NOT wired to an admin screen in
        this pass — see docs/architecture.md's Phase 3 section."""
        goal_setting = self._repo.get_goal_setting(assignment_id)
        if goal_setting is None:
            raise ValueError("No goal setting recorded for this assignment")
        goal_setting.frozen = False
        goal_setting.agreed_by = None
        goal_setting.agreed_at = None
        self._repo.update_goal_setting(goal_setting)
        return goal_setting

    def request_extension(
        self, assignment_id: UUID, requested_by: UUID, new_end_date: date
    ) -> Assignment:
        assignment = self._repo.get(assignment_id)
        self._engine.apply(
            assignment,
            "extension_requested",
            {"requested_by": requested_by, "new_end_date": new_end_date},
        )
        assignment.end_date = new_end_date
        self._repo.update(assignment)
        return assignment

    def close_assignment(
        self,
        assignment_id: UUID,
        objective_score: float,
        subjective_notes: str,
        reason: str = "completed",
        as_of: date | None = None,
    ) -> Assignment:
        assignment = self._repo.get(assignment_id)
        has_goal_setting = self._repo.get_goal_setting(assignment_id) is not None
        closure = ClosureRecord(
            assignment_id=assignment_id,
            objective_score=objective_score,
            subjective_notes=subjective_notes,
        )
        ctx: dict = {"closure": closure, "has_goal_setting": has_goal_setting}
        if as_of is not None:
            ctx["as_of"] = as_of
        self._engine.apply(assignment, "close_requested", ctx)
        assignment.closed_reason = reason
        self._repo.close_with_record(assignment, closure)
        return assignment

    def close_administratively(
        self, assignment_id: UUID, reason: str, notes: str | None = None
    ) -> Assignment:
        """Withdrawal or manager-departure closure: no score required, not
        gated by minimum-elapsed or goal-setting — these are
        administrative events, not performance assessments."""
        assignment = self._repo.get(assignment_id)
        self._engine.apply(assignment, "administrative_close", {})
        assignment.closed_reason = reason
        assignment.closure_note = notes
        self._repo.update(assignment)
        return assignment

    def withdraw_assignment(self, assignment_id: UUID, notes: str | None = None) -> Assignment:
        """The Agent left the program (or this rotation) early. Distinct
        from close_assignment: no fabricated performance score."""
        return self.close_administratively(assignment_id, reason="withdrawn", notes=notes)

    def reassign_all_from_departing_manager(
        self,
        old_manager_id: UUID,
        new_manager_id: UUID,
        notes: str | None = None,
        as_of: date | None = None,
    ) -> list[Assignment]:
        """The Manager is leaving. Close every one of their active
        Assignments (reason="manager_departed", no score required) and
        open a fresh Assignment for each Agent under the new manager,
        starting today (or `as_of`)."""
        if old_manager_id == new_manager_id:
            raise ValueError("new_manager_id must differ from the departing manager")

        start = as_of or today()
        new_assignments = []
        for assignment in self._repo.list_by_manager(old_manager_id):
            if assignment.state.value != "active":
                continue
            self.close_administratively(assignment.id, reason="manager_departed", notes=notes)
            new_assignments.append(
                self.create_assignment(
                    agent_id=assignment.agent_id,
                    manager_id=new_manager_id,
                    start_date=start,
                    kind=assignment.kind,
                )
            )
        return new_assignments

    def record_reverse_feedback(
        self, assignment_id: UUID, notes: str, as_of: date | None = None
    ) -> ReverseFeedback:
        assignment = self._repo.get(assignment_id)
        allowed, reason = guard_min_elapsed(
            self._min_days_before_closure, assignment, {"as_of": as_of} if as_of else {}
        )
        if not allowed:
            raise TransitionDenied(reason)
        feedback = ReverseFeedback(assignment_id=assignment_id, notes=notes)
        self._repo.add_reverse_feedback(feedback)
        return feedback

    # -- Review & Scoring (Phase 3) --

    def submit_review_score(
        self,
        assignment_id: UUID,
        criterion_scores: dict[str, float],
        notes: str,
        submitted_by: UUID,
    ) -> ReviewScore:
        """Manager's Review & Scoring submission for a still-ACTIVE
        Assignment — no admin gate on scoring itself (per spec). The
        objective score is always the simple average across
        `criterion_scores`, computed here rather than trusted from the
        caller. Frozen immediately on submission; a re-submission against
        an already-frozen score raises ReviewScoreFrozen — only
        reopen_review_score (admin) clears that."""
        self._repo.get(assignment_id)  # raises AssignmentNotFound if missing
        existing = self._repo.get_review_score(assignment_id)
        if existing is not None and existing.frozen:
            raise ReviewScoreFrozen(
                "This score is frozen — an admin must reopen it before it can be corrected"
            )
        objective_score = sum(criterion_scores.values()) / len(criterion_scores)
        review_score = ReviewScore(
            assignment_id=assignment_id,
            criterion_scores=dict(criterion_scores),
            objective_score=objective_score,
            notes=notes,
            submitted_by=submitted_by,
        )
        if existing is not None:
            self._repo.update_review_score(review_score)
        else:
            self._repo.add_review_score(review_score)
        return review_score

    def reopen_review_score(self, assignment_id: UUID) -> ReviewScore:
        """Admin-only action (not gated here — RBAC/UI enforces who may
        call this) that clears a score freeze so the manager can correct
        and resubmit. NOT wired to an admin screen in this pass — see
        docs/architecture.md's Phase 3 section."""
        review_score = self._repo.get_review_score(assignment_id)
        if review_score is None:
            raise ValueError("No review score recorded for this assignment")
        review_score.frozen = False
        self._repo.update_review_score(review_score)
        return review_score

    # -- Extension/Closure requests (Phase 3) --

    def request_change(
        self,
        assignment_id: UUID,
        request_type: RequestType,
        requested_by: UUID,
        new_end_date: date | None = None,
        notes: str = "",
    ) -> ChangeRequest:
        """Creates a PENDING ChangeRequest — does not itself extend or
        close anything (docs/associate_journey_redesign.md's "Extension /
        Closure" pattern: manager requests, admin approves, logged).
        Deliberately independent of the existing, direct
        `request_extension`/`close_assignment` calls, which keep their
        current unchanged behavior for whatever already depends on them.

        Only the assignment's own manager may request; a CLOSURE request
        additionally requires a frozen ReviewScore already on file (per
        spec: "after scoring, the manager requests closure") — an
        EXTENSION request needs `new_end_date`."""
        assignment = self._repo.get(assignment_id)
        if requested_by != assignment.manager_id:
            raise ValueError("Only the assignment's own manager may request this")
        if assignment.state.value != "active":
            raise ValueError("Only an active assignment can have a change requested")
        if request_type == RequestType.EXTENSION:
            if new_end_date is None:
                raise ValueError("new_end_date is required to request an extension")
            floor = assignment.end_date or assignment.start_date
            if new_end_date <= floor:
                raise ValueError(
                    f"An extension must move the end date later than {floor} (got {new_end_date})"
                )
        else:  # CLOSURE
            review_score = self._repo.get_review_score(assignment_id)
            if review_score is None or not review_score.frozen:
                raise ValueError(
                    "Submit and freeze a Review & Scoring score before requesting closure"
                )
        request = ChangeRequest(
            assignment_id=assignment_id,
            request_type=request_type,
            requested_by=requested_by,
            new_end_date=new_end_date,
            notes=notes,
        )
        self._repo.add_change_request(request)
        return request

    def list_change_requests(self, assignment_id: UUID) -> list[ChangeRequest]:
        return self._repo.list_change_requests(assignment_id)

    def list_pending_change_requests(self) -> list[ChangeRequest]:
        """Feed for a future admin-approval screen — not consumed by any
        UI yet. See ChangeRequest's docstring / docs/architecture.md's
        Phase 3 section for what's deferred."""
        return self._repo.list_pending_change_requests()

    def approve_change_request(self, request_id: UUID, decided_by: UUID) -> ChangeRequest:
        """Admin-only action (not gated here — RBAC/UI enforces who may
        call this; no admin screen calls it yet, see ChangeRequest's
        docstring). Approving an EXTENSION applies it via the existing
        direct extension path; approving a CLOSURE applies the
        assignment's frozen ReviewScore via the existing close_assignment
        path — this is the point the Agent actually moves to CLOSED
        (Available, for a Primary) per spec, not the request itself."""
        request = self._repo.get_change_request(request_id)
        if request is None:
            raise ValueError(f"ChangeRequest {request_id} not found")
        if request.status != RequestStatus.PENDING:
            raise ValueError("This request has already been decided")
        assignment = self._repo.get(request.assignment_id)
        if request.request_type == RequestType.EXTENSION:
            self.request_extension(
                request.assignment_id,
                requested_by=assignment.manager_id,
                new_end_date=request.new_end_date,
            )
        else:  # CLOSURE
            review_score = self._repo.get_review_score(request.assignment_id)
            if review_score is None:
                raise ValueError("No review score on file to close against")
            self.close_assignment(
                request.assignment_id,
                objective_score=review_score.objective_score,
                subjective_notes=review_score.notes,
            )
        request.status = RequestStatus.APPROVED
        request.decided_by = decided_by
        request.decided_at = datetime.now(timezone.utc)
        self._repo.update_change_request(request)
        return request

    def deny_change_request(
        self, request_id: UUID, decided_by: UUID, notes: str | None = None
    ) -> ChangeRequest:
        request = self._repo.get_change_request(request_id)
        if request is None:
            raise ValueError(f"ChangeRequest {request_id} not found")
        if request.status != RequestStatus.PENDING:
            raise ValueError("This request has already been decided")
        request.status = RequestStatus.DENIED
        request.decided_by = decided_by
        request.decided_at = datetime.now(timezone.utc)
        if notes:
            request.notes = f"{request.notes}\n[denied] {notes}".strip()
        self._repo.update_change_request(request)
        return request

    def list_overdue_goal_setting(
        self, older_than_days: int, as_of: date | None = None
    ) -> list[Assignment]:
        return self._repo.list_active_without_goal_setting(older_than_days, as_of=as_of)

    def list_overdue_closure(
        self, older_than_days: int | None = None, as_of: date | None = None
    ) -> list[Assignment]:
        """Assignments that are past the point they could have been
        closed and still aren't — a Manager who never got around to it.
        Defaults the threshold to double the minimum-elapsed period."""
        threshold = older_than_days if older_than_days is not None else self._min_days_before_closure * 2
        return self._repo.list_active_older_than(threshold, as_of=as_of)
