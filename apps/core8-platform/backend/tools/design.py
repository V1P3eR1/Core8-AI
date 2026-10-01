"""Head-of-Design tools — project workspace + design document management."""

import uuid
import aiosqlite
from database import get_db
from tools.registry import ToolDef, registry


async def write_design_doc(project: str, path: str, content: str) -> dict:
    """Create or overwrite a design document at the given path within a project."""
    if not project.strip() or not path.strip():
        return {"error": "project and path are required"}
    async with get_db() as db:
        await db.execute(
            """INSERT INTO design_docs (id, project, path, content)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(project, path) DO UPDATE SET
                 content=excluded.content,
                 updated_at=datetime('now')""",
            (str(uuid.uuid4()), project, path, content),
        )
        await db.commit()
    return {"written": f"{project}/{path}", "bytes": len(content)}


async def read_design_doc(project: str, path: str) -> dict:
    """Read a design document."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT content, updated_at FROM design_docs WHERE project=? AND path=?",
            (project, path),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Document '{project}/{path}' not found"}
    return {"project": project, "path": path, "content": row["content"], "updated_at": row["updated_at"]}


async def list_design_docs(project: str) -> list[dict]:
    """List all documents in a design project."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT path, length(content) as size_bytes, updated_at FROM design_docs WHERE project=? ORDER BY path",
            (project,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def list_design_projects() -> list[dict]:
    """List all design projects."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT project,
                      COUNT(*) as doc_count,
                      MAX(updated_at) as last_updated
               FROM design_docs GROUP BY project ORDER BY last_updated DESC""",
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def create_feature_spec(project: str, feature_slug: str, spec: str) -> dict:
    """Create or update a feature spec at features/<slug>.md within a project."""
    path = f"features/{feature_slug}.md"
    return await write_design_doc(project, path, spec)


async def delete_design_doc(project: str, path: str) -> dict:
    """Delete a design document."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM design_docs WHERE project=? AND path=?", (project, path)
        )
        await db.commit()
    return {"deleted": f"{project}/{path}"}


def register_design_tools():
    registry.register(ToolDef(
        name="write_design_doc",
        description=(
            "Create or overwrite a design document. Use paths like: "
            "'design.md', 'brief.md', 'features/hero.md', 'images/hero-desc.md'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name / slug (e.g. 'acme-landing')"},
                "path":    {"type": "string", "description": "File path within project"},
                "content": {"type": "string", "description": "Full document content (markdown)"},
            },
            "required": ["project", "path", "content"],
        },
        handler=write_design_doc,
    ))
    registry.register(ToolDef(
        name="read_design_doc",
        description="Read a design document by project and path.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "path":    {"type": "string"},
            },
            "required": ["project", "path"],
        },
        handler=read_design_doc,
    ))
    registry.register(ToolDef(
        name="list_design_docs",
        description="List all documents in a design project.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
            },
            "required": ["project"],
        },
        handler=list_design_docs,
    ))
    registry.register(ToolDef(
        name="list_design_projects",
        description="List all design projects with doc counts and last updated timestamps.",
        input_schema={"type": "object", "properties": {}},
        handler=list_design_projects,
    ))
    registry.register(ToolDef(
        name="create_feature_spec",
        description="Create or update a per-screen feature spec at features/<slug>.md.",
        input_schema={
            "type": "object",
            "properties": {
                "project":      {"type": "string"},
                "feature_slug": {"type": "string", "description": "kebab-case slug (e.g. 'hero-section')"},
                "spec":         {"type": "string", "description": "Full feature spec in markdown"},
            },
            "required": ["project", "feature_slug", "spec"],
        },
        handler=create_feature_spec,
    ))
    registry.register(ToolDef(
        name="delete_design_doc",
        description="Delete a design document.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "path":    {"type": "string"},
            },
            "required": ["project", "path"],
        },
        handler=delete_design_doc,
    ))
