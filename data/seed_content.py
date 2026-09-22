"""Idempotent, database-driven starter content for Phase 2."""

from __future__ import annotations

import re
import sqlite3
from typing import Any


CONTENT: dict[str, dict[str, list[str]]] = {
    "hr-screening": {
        "Self Introduction": [
            "30-second introduction", "60-second introduction", "120-second introduction",
            "Background", "Education", "Career story", "Current preparation",
            "Why SQL", "Why Data", "Why this role", "Why this company",
        ],
        "Project Introduction": [
            "Project overview", "Problem statement", "Dataset", "Technology stack",
            "Workflow", "Your contribution", "Results", "Business value",
        ],
        "Project Deep Dive": [
            "Architecture", "SQL implementation", "Data cleaning", "Analysis",
            "Validation", "Challenges", "Decisions", "Trade-offs", "Results",
        ],
        "Tricky Project Questions": [
            "Why did you choose this approach?", "What would you change?", "What failed?",
            "What was difficult?", "What if the data changed?",
            "What if performance became a problem?", "What would you improve?",
        ],
        "HR Follow-ups": [
            "Follow-up questions", "Deeper probing", "Clarification questions", "Challenge questions",
        ],
        "Career & Motivation": [
            "Career goals", "Why this career", "Why SQL/Data", "Why transition",
            "Short-term goals", "Long-term goals", "Motivation",
        ],
    },
    "non-technical-live-interview": {
        name: [f"{name} prompts"] for name in [
            "Strengths", "Weaknesses", "Hobbies", "Goals", "Motivation", "Career Transition",
            "Failure", "Conflict", "Teamwork", "Leadership", "Pressure", "Mistakes",
            "Feedback", "Handling Unknown Questions", "Difficult Situations", "Adaptability",
            "Learning Ability", "Communication", "Salary / HR", "Availability",
            "Workplace Behaviour", "Behavioural Follow-ups",
        ]
    },
}

SQL_MODULES: dict[str, list[str]] = {
    "SQL Fundamentals": ["What is SQL", "Databases and Tables", "Rows and Columns", "Primary Keys", "Foreign Keys", "Constraints", "NULL", "Data Types", "SQL Commands", "Relational Database Basics"],
    "SELECT & Filtering": ["SELECT", "DISTINCT", "WHERE", "Comparison Operators", "Logical Operators", "IN", "BETWEEN", "LIKE", "IS NULL", "ORDER BY", "LIMIT / TOP equivalents", "Aliases"],
    "Aggregation": ["COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP BY", "HAVING", "WHERE vs HAVING", "Aggregation mistakes"],
    "Joins": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "CROSS JOIN", "SELF JOIN", "Join conditions", "Multiple joins", "Join duplicates", "Join vs subquery"],
    "Subqueries": ["Scalar subqueries", "Single-row subqueries", "Multi-row subqueries", "Correlated subqueries", "EXISTS", "NOT EXISTS", "IN vs EXISTS", "Subquery vs JOIN"],
    "CTEs": ["What is a CTE", "Basic CTE", "Multiple CTEs", "CTE with aggregation", "CTE with joins", "Recursive CTE concept", "CTE vs subquery", "CTE vs temporary table"],
    "CASE Expressions": ["Basic CASE", "Searched CASE", "CASE with aggregation", "CASE with GROUP BY", "CASE with NULL", "Conditional categorization", "Business-rule examples"],
    "String Functions": ["CONCAT", "LENGTH", "UPPER / LOWER", "TRIM", "SUBSTRING", "LEFT / RIGHT", "REPLACE", "String pattern matching", "Practical cleaning examples"],
    "Date & Time": ["Date types", "Current date/time", "Date extraction", "Date arithmetic", "Date differences", "Month/year filtering", "Date grouping", "Date-based business problems"],
    "Window Functions": ["Window-function concept", "OVER()", "PARTITION BY", "ORDER BY inside window", "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "Running totals", "Moving averages", "Top-N per group", "Window functions vs GROUP BY"],
    "Set Operations": ["UNION", "UNION ALL", "INTERSECT", "EXCEPT", "Set-operation requirements", "UNION vs UNION ALL", "Practical examples"],
    "Data Modification": ["INSERT", "UPDATE", "DELETE", "Conditional UPDATE", "Conditional DELETE", "Safe data modification", "Transactions with modifications"],
    "Database Design": ["Database design basics", "Entity relationships", "Primary key design", "Foreign key design", "One-to-one", "One-to-many", "Many-to-many", "Junction tables", "Normalization", "1NF", "2NF", "3NF", "Denormalization"],
    "Views / Procedures / Functions": ["Views", "View use cases", "Stored procedures", "Functions", "Procedure vs function", "Advantages", "Limitations", "Practical use"],
    "Indexes & Performance": ["What is an index", "Why indexes help", "Index trade-offs", "Composite indexes", "Index selection", "Query performance", "EXPLAIN concept", "Full table scans", "Common performance mistakes"],
    "Transactions": ["Transactions", "COMMIT", "ROLLBACK", "ACID", "Atomicity", "Consistency", "Isolation", "Durability", "Transaction examples", "Practical transaction problems"],
    "Common SQL Mistakes": ["NULL mistakes", "JOIN mistakes", "Duplicate rows", "Incorrect GROUP BY", "WHERE/HAVING confusion", "Aggregation mistakes", "Window-function mistakes", "Date filtering mistakes", "Implicit conversions", "Performance mistakes"],
    "SQL Interview Tricks": ["Common interviewer traps", "Output prediction", "NULL traps", "JOIN traps", "GROUP BY traps", "Window-function traps", "Subquery traps", "Performance traps", "Requirement interpretation", "Edge cases"],
}

# Phase 4 keeps the SQL curriculum broad and explicit for the Technical Round.
TECHNICAL_MODULES = SQL_MODULES

# Phase 5 uses a deliberately explicit project curriculum.  The names are
# stable seed identifiers; topics can be extended without changing the schema.
PROJECT_MODULES: dict[str, list[str]] = {
    "Project Introduction": [
        "30-second introduction", "1-minute explanation", "2-minute explanation",
        "Project objective", "Business problem", "Project scope", "Project outcome",
    ],
    "Project Architecture": [
        "Data flow", "Input and data sources", "Database", "Tables",
        "Transformations", "Analysis", "Output and reporting", "Architecture explanation",
    ],
    "Project Deep Dive": [
        "Why this project", "Why this dataset", "Schema", "Important tables",
        "Relationships", "Important queries", "Calculations", "Assumptions", "Decisions",
    ],
    "SQL in Project": [
        "Joins used", "Aggregations", "CTEs", "Subqueries", "Window functions",
        "CASE expressions", "Date logic", "Data cleaning", "Optimization", "Query debugging",
    ],
    "Data Cleaning & Quality": [
        "Duplicates", "NULL values", "Inconsistent values", "Missing data",
        "Invalid records", "Data types", "Outliers", "Validation", "Quality checks",
    ],
    "Business Analysis": [
        "KPIs", "Revenue", "Customers", "Orders", "Products", "Retention",
        "Trends", "Segmentation", "Business questions", "Insights",
    ],
    "Practical SQL Scenarios": [
        "Query from requirements", "Debug a query", "Optimize a slow query",
        "Explain query output", "Handle duplicate rows", "Handle NULL values",
        "Identify missing records", "Calculate business metrics", "Compare periods",
        "Rank entities", "Top-N analysis",
    ],
    "Project Troubleshooting": [
        "Wrong result", "Unexpected duplicates", "Missing rows", "Incorrect joins",
        "Incorrect aggregation", "Performance issue", "Data mismatch",
        "Business requirement mismatch",
    ],
    "Project Challenges": [
        "Difficult problem", "Limitation", "Trade-off", "Failed approach",
        "Correction", "Validation", "Lessons learned",
    ],
    "Project Follow-ups": [
        "Interviewer follow-up questions", "Deeper SQL questions", "Business follow-ups",
        "Architecture follow-ups", "Data-quality follow-ups", "Optimization follow-ups",
    ],
}
# Descriptive alias for tests and integrations that refer to the category name.
PROJECT_PRACTICAL_MODULES = PROJECT_MODULES


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _starter_question(category_slug: str, module_name: str, topic_name: str,
                      category_id: int, module_id: int, topic_id: int) -> tuple[Any, ...]:
    if category_slug == "hr-screening":
        question = f"How would you discuss {topic_name} in an interview?"
        answer = "Use a direct answer, one truthful example or placeholder, the result, and a connection to the role."
        explanation = "Replace bracketed guidance with your own experience; do not invent personal facts."
        trick = "Keep the response concise, concrete, and natural rather than memorized."
    else:
        question = f"Tell me about {module_name.lower()}."
        answer = "Give a direct answer, support it with a truthful example, and explain what you learned or achieved."
        explanation = "Use your own experience or keep [Your example] until you have a truthful example to add."
        trick = "Acknowledge what you know, ask a clarifying question, and avoid guessing."
    return (
        category_id, module_id, topic_id, question, answer, explanation, None,
        "behavioral", "easy", trick,
        "What is a specific example, and what would you do differently next time?",
        "hr, behavioural, communication, starter",
    )


def seed_content(connection: sqlite3.Connection) -> None:
    """Create required hierarchy and one editable starter question per topic."""
    categories = {row["slug"]: row["id"]
                  for row in connection.execute("SELECT id, slug FROM categories")}
    for category_slug, modules in CONTENT.items():
        category_id = categories.get(category_slug)
        if category_id is None:
            continue
        for module_order, (module_name, topics) in enumerate(modules.items(), 1):
            module_slug = _slug(module_name)
            connection.execute(
                """INSERT INTO modules(category_id, name, slug, description, sort_order)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(category_id, slug) DO UPDATE SET name=excluded.name,
                   description=excluded.description, sort_order=excluded.sort_order""",
                (category_id, module_name, module_slug,
                 "Starter interview preparation module.", module_order),
            )
            module_id = connection.execute(
                "SELECT id FROM modules WHERE category_id=? AND slug=?",
                (category_id, module_slug),
            ).fetchone()["id"]
            for topic_order, topic_name in enumerate(topics, 1):
                topic_slug = _slug(topic_name)
                connection.execute(
                    """INSERT INTO topics(module_id, name, slug, description, sort_order)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(module_id, slug) DO UPDATE SET name=excluded.name,
                       description=excluded.description, sort_order=excluded.sort_order""",
                    (module_id, topic_name, topic_slug,
                     "Add your own truthful preparation notes.", topic_order),
                )
                topic_id = connection.execute(
                    "SELECT id FROM topics WHERE module_id=? AND slug=?",
                    (module_id, topic_slug),
                ).fetchone()["id"]
                question = _starter_question(
                    category_slug, module_name, topic_name,
                    category_id, module_id, topic_id,
                )
                exists = connection.execute(
                    """SELECT id FROM questions
                       WHERE category_id=? AND module_id=? AND topic_id=? AND question=?""",
                    question[:4],
                ).fetchone()
                if exists is None:
                    cursor = connection.execute(
                        """INSERT INTO questions(
                           category_id, module_id, topic_id, question, answer, explanation,
                           personal_answer, question_type, difficulty, interview_trick, follow_up)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        question[:6] + (question[6],) + question[7:11],
                    )
                    question_id = cursor.lastrowid
                    for tag in question[11].split(", "):
                        connection.execute(
                            "INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                            (tag,),
                        )
                        tag_id = connection.execute(
                            "SELECT id FROM tags WHERE name=?", (tag,)
                        ).fetchone()["id"]
                        connection.execute(
                            "INSERT OR IGNORE INTO question_tags(question_id, tag_id) VALUES (?, ?)",
                            (question_id, tag_id),
                        )
    _seed_sql(connection, categories.get("sql-technical-notes"))
    _seed_technical(connection, categories.get("technical-round"))
    _seed_project(connection, categories.get("project-practical"))


def _seed_sql(connection: sqlite3.Connection, category_id: int | None) -> None:
    if category_id is None:
        return
    for module_order, (module_name, topics) in enumerate(SQL_MODULES.items(), 1):
        module_slug = _slug(module_name)
        connection.execute(
            """INSERT INTO modules(category_id, name, slug, description, sort_order)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(category_id, slug) DO UPDATE SET name=excluded.name,
               description=excluded.description, sort_order=excluded.sort_order""",
            (category_id, module_name, module_slug, "MySQL 8 SQL technical manual module.", module_order),
        )
        module_id = connection.execute(
            "SELECT id FROM modules WHERE category_id=? AND slug=?", (category_id, module_slug)
        ).fetchone()["id"]
        for topic_order, topic_name in enumerate(topics, 1):
            topic_slug = _slug(topic_name)
            connection.execute(
                """INSERT INTO topics(module_id, name, slug, description, sort_order)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(module_id, slug) DO UPDATE SET name=excluded.name,
                   description=excluded.description, sort_order=excluded.sort_order""",
                (module_id, topic_name, topic_slug, "Concept, mental model, syntax, example, use, mistakes, and memory trick.", topic_order),
            )
            topic_id = connection.execute(
                "SELECT id FROM topics WHERE module_id=? AND slug=?", (module_id, topic_slug)
            ).fetchone()["id"]
            syntax = f"-- MySQL 8\nSELECT * FROM sample_table /* {topic_name} */;"
            body = (f"{topic_name} is a practical SQL building block. Mental model: "
                    "shape rows first, then transform, combine, or summarize them.")
            _insert_once(connection, "notes", "topic_id", topic_id, "Concept and mental model", body)
            _insert_once(connection, "notes", "topic_id", topic_id, "Syntax", syntax)
            _insert_once(connection, "notes", "topic_id", topic_id, "Real-world use",
                         "Use it in reporting, data quality checks, analytics pipelines, or interview exercises.")
            _insert_once(connection, "notes", "topic_id", topic_id, "Common mistakes",
                         "Check row grain, NULL behavior, duplicate rows, and whether filters belong before or after aggregation.")
            _insert_once(connection, "examples", "topic_id", topic_id, "Worked example",
                         f"{syntax}\n\n-- Replace sample_table and columns with your schema.")
            _insert_once(connection, "tricks", "topic_id", topic_id, "Memory trick",
                         f"Remember {topic_name}: state the grain, write the smallest query, then validate the result.")
            question_templates = (
                (f"What is {topic_name}, and when would you use it?", "Conceptual", "easy"),
                (f"Write a MySQL 8 example using {topic_name}.", "Query Writing", "medium"),
                (f"What edge case or performance issue can arise with {topic_name}?", "Tricky", "hard"),
            )
            for question_text, question_type, difficulty in question_templates:
                existing = connection.execute(
                    "SELECT id FROM questions WHERE category_id=? AND module_id=? AND topic_id=? AND question=?",
                    (category_id, module_id, topic_id, question_text),
                ).fetchone()
                if existing is None:
                    qid = connection.execute(
                    """INSERT INTO questions(category_id,module_id,topic_id,question,answer,explanation,
                       question_type,difficulty,interview_trick,follow_up)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (category_id, module_id, topic_id, question_text,
                     f"Explain {topic_name}, show valid MySQL 8 syntax, and connect it to customers, orders, employees, or sales.",
                     body, question_type, difficulty, "State the row grain and NULL behavior before writing SQL.",
                     f"What mistake commonly occurs with {topic_name}?"),
                    ).lastrowid
                    for tag in ("sql", "technical", _slug(module_name)):
                        connection.execute("INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (tag,))
                        tid = connection.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()[0]
                        connection.execute("INSERT OR IGNORE INTO question_tags(question_id,tag_id) VALUES (?,?)", (qid, tid))
                    connection.execute("INSERT INTO followups(question_id,question,answer) VALUES (?,?,?)",
                                       (qid, f"Give a real-world use for {topic_name}.", "Use a concrete reporting or data-quality scenario."))


def _seed_technical(connection: sqlite3.Connection, category_id: int | None) -> None:
    if category_id is None:
        return
    for module_order, (module_name, topics) in enumerate(TECHNICAL_MODULES.items(), 1):
        module_slug = _slug(module_name)
        connection.execute(
            """INSERT INTO modules(category_id,name,slug,description,sort_order)
               VALUES (?,?,?,?,?) ON CONFLICT(category_id,slug) DO UPDATE SET
               name=excluded.name, description=excluded.description, sort_order=excluded.sort_order""",
            (category_id, module_name, module_slug, "Technical-round SQL interview practice.", module_order))
        module_id = connection.execute(
            "SELECT id FROM modules WHERE category_id=? AND slug=?", (category_id, module_slug)).fetchone()["id"]
        for topic_order, topic_name in enumerate(topics, 1):
            topic_slug = _slug(topic_name)
            connection.execute(
                """INSERT INTO topics(module_id,name,slug,description,sort_order)
                   VALUES (?,?,?,?,?) ON CONFLICT(module_id,slug) DO UPDATE SET
                   name=excluded.name, description=excluded.description, sort_order=excluded.sort_order""",
                (module_id, topic_name, topic_slug, "Interview question, reasoning, SQL solution, trap, and follow-up.", topic_order))
            topic_id = connection.execute(
                "SELECT id FROM topics WHERE module_id=? AND slug=?", (module_id, topic_slug)).fetchone()["id"]
            rows = (
                (f"Explain {topic_name} and when you would use it.", "Conceptual", "easy", "Explain the concept, then state row grain and NULL behavior."),
                (f"Write a MySQL 8 query demonstrating {topic_name}.", "Query writing", "medium", "Talk through the plan before writing SQL and validate with a small example."),
                (f"What is a common production trap with {topic_name}?", "Troubleshooting", "hard", "Mention duplicates, edge cases, and performance trade-offs."),
                (f"What output would you expect when {topic_name} is applied to duplicate and NULL data?", "Output Prediction", "medium", "State the input assumptions, then reason row by row before giving the result."),
                (f"How would you use {topic_name} to solve a customer, order, or employee reporting problem?", "Real World", "medium", "Translate the business requirement into a row grain, joins, filters, and validation checks."),
                (f"How would you debug a query involving {topic_name} that returns the wrong rows?", "Debugging", "hard", "Isolate the smallest failing case and inspect joins, predicates, aggregation, and NULL handling."),
                (f"How would you optimize a slow query that uses {topic_name} on a large table?", "Optimization", "hard", "Compare the execution plan, access paths, selectivity, and whether the query can reduce rows earlier."),
                (f"Can you solve a {topic_name} problem without using the most obvious SQL feature?", "Problem Solving", "hard", "Offer a correct alternative and explain its readability and performance trade-offs."),
                (f"What follow-up requirement could change your {topic_name} solution?", "Follow-up", "medium", "Ask about ties, missing data, time boundaries, scale, and the expected output grain."),
            )
            for question_text, qtype, difficulty, approach in rows:
                existing = connection.execute(
                    "SELECT id FROM questions WHERE category_id=? AND module_id=? AND topic_id=? AND question=?",
                    (category_id, module_id, topic_id, question_text)).fetchone()
                if existing:
                    continue
                qid = connection.execute(
                    """INSERT INTO questions(category_id,module_id,topic_id,question,answer,explanation,
                       question_type,difficulty,interview_trick,follow_up,interviewer_expectation,
                       thinking_approach,sql_solution,alternative_solution,common_trap,interview_style,source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (category_id, module_id, topic_id, question_text,
                     f"Give a precise definition of {topic_name}, a MySQL 8 example, and a practical use.",
                     "A strong answer is correct, scoped to the stated schema, and calls out edge cases.",
                     qtype, difficulty, "Clarify the grain and requirements before coding.",
                     f"How would you test or optimize {topic_name}?",
                     "Define the expected result and explain trade-offs.",
                     approach, f"-- MySQL 8 example for {topic_name}\nSELECT ...;",
                     "Use a CTE or window function when it makes the intent clearer.",
                     f"Watch for NULLs, duplicate rows, and incorrect filtering around {topic_name}.",
                     "technical", "phase-4-seed"),
                ).lastrowid
                for tag in ("sql", "technical-round", _slug(module_name), _slug(qtype)):
                    connection.execute("INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (tag,))
                    tag_id = connection.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()["id"]
                    connection.execute("INSERT OR IGNORE INTO question_tags(question_id,tag_id) VALUES (?,?)",
                                       (qid, tag_id))
                connection.execute(
                    "INSERT INTO followups(question_id,question,answer) VALUES (?,?,?)",
                    (qid, f"How would you adapt this for a larger dataset involving {topic_name}?",
                     "State an indexing, validation, or batching consideration."))


def _insert_once(connection: sqlite3.Connection, table: str, key: str, key_id: int, title: str, body: str) -> None:
    if connection.execute(f"SELECT 1 FROM {table} WHERE {key}=? AND title=?", (key_id, title)).fetchone() is None:
        connection.execute(f"INSERT INTO {table}({key},title,body) VALUES (?,?,?)", (key_id, title, body))


def _seed_project(connection: sqlite3.Connection, category_id: int | None) -> None:
    """Seed realistic, reusable project-practice content without user-specific claims."""
    if category_id is None:
        return
    styles = (
        "project-explanation", "project-explanation", "business-scenario",
        "sql-practical", "data-quality", "business-scenario",
        "project-explanation", "follow-up",
    )
    templates = (
        ("Project explanation", "Explain {topic} in your project.",
         "Use a truthful project or clearly label [example project]. State the context, action, result, and lesson.",
         "Start with the business goal and row grain; avoid listing tools without explaining decisions.",
         "A concise answer has context, approach, validation, result, and one trade-off.",
         "Do not invent a metric, employer, dataset, or personal responsibility."),
        ("SQL practical", "How would you implement {topic} in SQL?",
         "Clarify the required output grain, identify keys, write a small query, and validate it on edge cases.",
         "Name the tables and grain before writing joins. Show a concrete MySQL 8 pattern using generic table names.",
         "Prefer readable CTEs, explicit joins, and predicates that match the requirement.",
         "Watch for join multiplication, NULL semantics, date boundaries, and ties."),
        ("Business scenario", "A stakeholder asks about {topic}; how would you investigate?",
         "Translate the request into a measurable definition, assumptions, data checks, analysis, and an actionable conclusion.",
         "Ask clarifying questions about scope, time window, population, and success metric before querying.",
         "Separate observed facts from interpretation and label any practice scenario as an example.",
         "Do not claim stakeholder outcomes or business results that are not documented."),
        ("Data quality", "How would you validate {topic} before sharing the result?",
         "Check completeness, uniqueness, referential integrity, freshness, reconciliation totals, and representative samples.",
         "Define a pass/fail rule, compare with a trusted control total, and record exceptions.",
         "Show how a bad result would be detected and communicated before it reaches a dashboard.",
         "A plausible number is not proof of correctness."),
        ("Debugging", "What would you do if a project query involving {topic} returned unexpected results?",
         "Reproduce the issue with a small sample, verify grain and joins, isolate each predicate, then compare to an expected control.",
         "Change one assumption at a time and keep the failing example so the fix is testable.",
         "Explain both the immediate fix and the regression check.",
         "Do not silently remove rows or change definitions to make the output look right."),
        ("Trade-off", "What trade-off could arise when handling {topic}?",
         "Discuss accuracy, freshness, maintainability, cost, performance, and stakeholder usability, then justify the chosen balance.",
         "State the constraint, alternatives considered, decision, and how you would revisit it.",
         "A good answer acknowledges limitations rather than presenting one approach as universally best.",
         "Avoid claiming production scale, tools, or impact without evidence."),
        ("Follow-up", "What follow-up requirement would change your approach to {topic}?",
         "Ask about late data, ties, missing values, changing definitions, scale, access, and required delivery time.",
         "Describe the smallest design change and the validation it would require.",
         "Keep the answer conditional: if the requirement changes, the design changes.",
         "Do not guess hidden requirements; ask a focused clarification question."),
        ("Reflection", "What did you learn from working on {topic}?",
         "Use a truthful experience or the explicit placeholder [your example]. Explain the initial assumption, evidence, and changed practice.",
         "Connect the lesson to a repeatable habit such as documenting grain or adding a quality check.",
         "Reflection should be specific without fabricating a personal story.",
         "Never present this seed scenario as the user's own experience."),
    )
    for module_order, (module_name, topics) in enumerate(PROJECT_MODULES.items(), 1):
        module_slug = _slug(module_name)
        connection.execute(
            """INSERT INTO modules(category_id,name,slug,description,sort_order)
               VALUES (?,?,?,?,?) ON CONFLICT(category_id,slug) DO UPDATE SET
               name=excluded.name, description=excluded.description, sort_order=excluded.sort_order""",
            (category_id, module_name, module_slug,
             "Project and practical interview preparation; examples are templates or practice scenarios.", module_order),
        )
        module_id = connection.execute(
            "SELECT id FROM modules WHERE category_id=? AND slug=?", (category_id, module_slug)
        ).fetchone()["id"]
        for topic_order, topic_name in enumerate(topics, 1):
            topic_slug = _slug(topic_name)
            connection.execute(
                """INSERT INTO topics(module_id,name,slug,description,sort_order)
                   VALUES (?,?,?,?,?) ON CONFLICT(module_id,slug) DO UPDATE SET
                   name=excluded.name, description=excluded.description, sort_order=excluded.sort_order""",
                (module_id, topic_name, topic_slug,
                 "Use the guidance as a template; replace placeholders only with truthful facts.", topic_order),
            )
            topic_id = connection.execute(
                "SELECT id FROM topics WHERE module_id=? AND slug=?", (module_id, topic_slug)
            ).fetchone()["id"]
            _insert_once(connection, "notes", "topic_id", topic_id, "Answer structure",
                         f"Template for {topic_name}: context → approach → validation → result → limitation. "
                         "This is guidance, not a claim about the learner's experience.")
            _insert_once(connection, "notes", "topic_id", topic_id, "Truthful example guidance",
                         "Practice scenario/template only. Replace [your example] with a verified personal example or leave it as a placeholder.")
            _insert_once(connection, "examples", "topic_id", topic_id, "Reusable project explanation template",
                         f"Situation: [project or practice scenario]\nTask: [business question]\n"
                         f"Action: [what you did for {topic_name}]\nResult: [verified result or expected check]\n"
                         "Reflection: [what you learned].")
            for index, (label, question, answer, approach, expectation, trap) in enumerate(templates):
                question_text = f"[{module_name}] {question.format(topic=topic_name)}"
                existing = connection.execute(
                    "SELECT id FROM questions WHERE category_id=? AND module_id=? AND topic_id=? AND question=?",
                    (category_id, module_id, topic_id, question_text)).fetchone()
                if existing:
                    continue
                difficulty = ("easy", "medium", "hard")[index % 3]
                style = styles[index]
                qid = connection.execute(
                    """INSERT INTO questions(category_id,module_id,topic_id,question,answer,explanation,
                       question_type,difficulty,interview_trick,follow_up,interviewer_expectation,
                       thinking_approach,sql_solution,alternative_solution,common_trap,interview_style,source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (category_id, module_id, topic_id, question_text, answer,
                     "Practice template/scenario; do not treat it as a user fact.",
                     label, difficulty,
                     "Label assumptions and distinguish an example from lived experience.",
                     f"How would you validate or adapt your answer for {topic_name}?",
                     expectation, approach,
                     f"-- Illustrative MySQL 8 pattern for {topic_name}\n"
                     "SELECT key_column, COUNT(*) AS row_count\nFROM example_table\nGROUP BY key_column;",
                     "Use a CTE, a control total, or a documented validation query when clearer.",
                     trap, style, "phase-5-seed"),
                ).lastrowid
                for tag in ("project", "practical", style, _slug(module_name), _slug(label)):
                    connection.execute("INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (tag,))
                    tag_id = connection.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()["id"]
                    connection.execute("INSERT OR IGNORE INTO question_tags(question_id,tag_id) VALUES (?,?)",
                                       (qid, tag_id))
                connection.execute(
                    "INSERT INTO followups(question_id,question,answer) VALUES (?,?,?)",
                    (qid, f"What evidence would support your answer about {topic_name}?",
                     "Name the data check, sample, control total, or documented assumption you would use.")) 
