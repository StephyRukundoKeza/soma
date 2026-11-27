"""Create a SOMA account. The password is typed in privately and never saved in the project.

    python scripts/add_user.py admin stephy "Stephy"
    python scripts/add_user.py teacher mwarimu "Mwarimu"
    python scripts/add_user.py learner aline "Aline"

Teachers can then add learners from the app, or share their class code.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import accounts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Create an admin, teacher or learner account in Supabase.")
    parser.add_argument("role", choices=accounts.ROLES)
    parser.add_argument("username", help="what the person types to log in, e.g. aline")
    parser.add_argument("name", help="name shown in the app; a first name or nickname is enough")
    args = parser.parse_args()

    password = getpass.getpass("Password (at least 8 characters, hidden while typing): ")
    if password != getpass.getpass("Type it again: "):
        sys.exit("The two passwords are different.")

    messages = {"short_password": "Not created: the password needs at least 8 characters.",
                "username_taken": "Not created: this username already exists.",
                "unknown_role": "Not created: the role must be admin, teacher or learner."}
    try:
        user = accounts.create_user(args.username, password, args.role, args.name)
    except accounts.AccountError as error:
        sys.exit(messages.get(str(error), f"Not created: {error}"))
    print(f"Created {user['role']} account '{args.username}' ({user['name']}).")


if __name__ == "__main__":
    main()
