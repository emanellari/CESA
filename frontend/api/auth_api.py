from api.client import api_post


def login_user(email: str, password: str):
    return api_post("/auth/login", json={"email": email, "password": password})


def signup_user(email: str, password: str):
    return api_post("/auth/signup", json={"email": email, "password": password})