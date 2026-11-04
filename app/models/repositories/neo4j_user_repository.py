"""Neo4j-implementasjon av UserRepository: (:User {id, email, name, phone, password_hash, role})."""
from dataclasses import replace

from neo4j.exceptions import ConstraintError

from app.models.errors import DuplicateEmailError
from app.models.repositories import neo4j_connection as db
from app.models.repositories.base import UserRepository
from app.models.user import Role, User, normalize_email

GET_BY_ID = "MATCH (u:User {id: $id}) RETURN u {.*} AS user"
GET_BY_EMAIL = "MATCH (u:User {email: $email}) RETURN u {.*} AS user"
CREATE_USER = (
    "CREATE (u:User {id: $id, email: $email, name: $name, phone: $phone,"
    " password_hash: $password_hash, role: $role})"
)


class Neo4jUserRepository(UserRepository):
    def get_by_id(self, user_id):
        return _first_user(db.run_read(GET_BY_ID, id=user_id))

    def get_by_email(self, email):
        return _first_user(db.run_read(GET_BY_EMAIL, email=normalize_email(email)))

    def add(self, user):
        def work(tx):
            user_id = db.next_id(tx, "User")
            tx.run(
                CREATE_USER,
                id=user_id,
                email=user.email,
                name=user.name,
                phone=user.phone,
                password_hash=user.password_hash,
                role=user.role.value,
            )
            return user_id

        try:
            user_id = db.write_transaction(work)
        except ConstraintError as error:  # unikhets-constraint på User.email
            raise DuplicateEmailError(user.email) from error
        return replace(user, id=user_id)


def _first_user(records):
    if not records:
        return None
    props = records[0]["user"]
    return User(
        id=props["id"],
        email=props["email"],
        name=props["name"],
        phone=props.get("phone"),
        password_hash=props["password_hash"],
        role=Role(props["role"]),
    )
