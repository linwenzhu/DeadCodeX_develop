from fastapi import FastAPI

app = FastAPI()


def serialize_user(user_id):
    return {"id": user_id, "active": True}


@app.get("/users/{user_id}")
def read_user(user_id):
    return serialize_user(user_id)


def old_format_user(user_id):
    return f"legacy-user-{user_id}"
