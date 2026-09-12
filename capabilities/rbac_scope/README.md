# rbac_scope

Block 6: computes "can Viewer X see Record Y" from the Viewer's
relationship to the record (owns / assigned-to), never from a hardcoded
per-role query. Owns no business logic — it wraps another block's repo
and service.

Depends on `assignment` at runtime (imports `assignment.domain`,
`assignment.ports`, `assignment.service`). Not declared in
`pyproject.toml` as a normal PyPI dependency because these are sibling
packages in the same monorepo, not published — install both in the same
environment:

```
pip install -e ../assignment -e ../party_identity -e .[test]
```
