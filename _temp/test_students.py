import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from agent.tools import show_students

async def main():
    # Test 1: by class name
    r = await show_students(class_name="高一一班")
    print("Test 1 (高一一班):", r[:200])

    # Test 2: empty
    r = await show_students()
    print("Test 2 (empty):", r[:200])

    # Test 3: check what classes exist
    from app.models.database import get_db
    from sqlalchemy import text
    session = next(get_db())
    rows = session.execute(text("SELECT class_id, name FROM classes")).fetchall()
    session.close()
    print("Available classes:", [(r[0], r[1]) for r in rows])

asyncio.run(main())
