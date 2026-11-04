"""Neo4j-implementasjon av QuestionRepository (design.md §7).

(:User)-[:ASKED]->(:Question)-[:ABOUT]->(:Order), (:Answer)-[:ANSWERS]->(:Question), (:User)-[:WROTE]->(:Answer).
Answer.question_id har en unikhets-constraint, så databasen sikrer maks ett svar per spørsmål.
"""
from dataclasses import replace

from neo4j.exceptions import ConstraintError

from app.models.errors import AlreadyAnsweredError
from app.models.question import Answer, Question
from app.models.repositories import neo4j_connection as db
from app.models.repositories.base import QuestionRepository
from app.models.user import Role, User

CREATE_QUESTION = (
    "MATCH (u:User {id: $user_id}), (o:Order {id: $order_id})"
    " CREATE (u)-[:ASKED]->(q:Question {id: $id, text: $text, asked_at: $asked_at})-[:ABOUT]->(o)"
    " RETURN q.id AS id"
)
CREATE_ANSWER = (
    "MATCH (q:Question {id: $question_id}) OPTIONAL MATCH (w:User {id: $user_id})"
    " CREATE (a:Answer {question_id: $question_id, text: $text, answered_at: $answered_at})-[:ANSWERS]->(q)"
    " FOREACH (writer IN CASE WHEN w IS NULL THEN [] ELSE [w] END | CREATE (writer)-[:WROTE]->(a))"
    " RETURN a.question_id AS question_id"
)

# Spørsmålet med ordre, kunde og eventuelt svar.
_WITH_ALL = (
    " OPTIONAL MATCH (u:User)-[:ASKED]->(q)"
    " OPTIONAL MATCH (a:Answer)-[:ANSWERS]->(q)"
    " OPTIONAL MATCH (w:User)-[:WROTE]->(a)"
    " WITH q, o, u, a, w"
)
_RETURN = (
    " RETURN q {.*} AS question, o.id AS order_id, u.id AS user_id,"
    " u {.id, .email, .name, .phone, .role} AS customer,"
    " a {.text, .answered_at} AS answer, w.id AS answer_user_id"
)

GET = "MATCH (q:Question {id: $id})-[:ABOUT]->(o:Order)" + _WITH_ALL + _RETURN
LIST_FOR_ORDER = (
    "MATCH (q:Question)-[:ABOUT]->(o:Order {id: $order_id})" + _WITH_ALL + _RETURN + " ORDER BY q.asked_at, q.id"
)
LIST_UNANSWERED = (
    "MATCH (q:Question)-[:ABOUT]->(o:Order)" + _WITH_ALL + " WHERE a IS NULL" + _RETURN + " ORDER BY q.asked_at, q.id"
)
LIST_ANSWERED = (
    "MATCH (q:Question)-[:ABOUT]->(o:Order)"
    + _WITH_ALL
    + " WHERE a IS NOT NULL"
    + _RETURN
    + " ORDER BY a.answered_at DESC, q.id DESC LIMIT $limit"
)
COUNT_UNANSWERED = (
    "MATCH (q:Question) WHERE NOT EXISTS { (:Answer)-[:ANSWERS]->(q) } RETURN count(q) AS unanswered"
)


class Neo4jQuestionRepository(QuestionRepository):
    def add(self, question):
        def work(tx):
            question_id = db.next_id(tx, "Question")
            record = tx.run(
                CREATE_QUESTION,
                id=question_id,
                user_id=question.user_id,
                order_id=question.order_id,
                text=question.text,
                asked_at=question.asked_at,
            ).single()
            if record is None:
                raise LookupError("Fant ikke kunden eller bestillingen; spørsmålet er ikke lagret.")
            return question_id

        return replace(question, id=db.write_transaction(work))

    def get(self, question_id):
        records = db.run_read(GET, id=question_id)
        return _to_question(records[0]) if records else None

    def list_for_order(self, order_id):
        return [_to_question(r) for r in db.run_read(LIST_FOR_ORDER, order_id=order_id)]

    def list_unanswered(self):
        return [_to_question(r) for r in db.run_read(LIST_UNANSWERED)]

    def list_answered(self, limit=20):
        return [_to_question(r) for r in db.run_read(LIST_ANSWERED, limit=limit)]

    def save_answer(self, question):
        answer = question.answer
        try:
            record = db.run_write(
                CREATE_ANSWER,
                question_id=question.id,
                user_id=answer.user_id,
                text=answer.text,
                answered_at=answer.answered_at,
            )
        except ConstraintError as error:  # unikhets-constraint på Answer.question_id
            raise AlreadyAnsweredError() from error
        if not record:
            raise LookupError(f"Fant ikke spørsmålet {question.id}; svaret er ikke lagret.")

    def count_unanswered(self):
        return db.run_read(COUNT_UNANSWERED)[0]["unanswered"]


def _to_question(record):
    props = record["question"]
    answer = None
    if record["answer"] is not None:
        answer = Answer(
            text=record["answer"]["text"],
            answered_at=_native(record["answer"]["answered_at"]),
            user_id=record["answer_user_id"],
        )
    return Question(
        id=props["id"],
        order_id=record["order_id"],
        user_id=record["user_id"],
        text=props["text"],
        asked_at=_native(props["asked_at"]),
        answer=answer,
        customer=_to_customer(record["customer"]),
    )


def _to_customer(props):
    if props is None:
        return None
    return User(
        id=props["id"],
        email=props["email"],
        name=props["name"],
        phone=props.get("phone"),
        password_hash="",
        role=Role(props["role"]),
    )


def _native(value):
    """neo4j.time.DateTime -> datetime.datetime (lokal tid, som satt i modellen)."""
    return value.to_native() if hasattr(value, "to_native") else value
