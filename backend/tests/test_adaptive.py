"""
Tests for Adaptive Learning Features:
1. Progression logic: calculate_next_level(current_level, score_percentage)
2. Content generation: generate_adaptive_content(topic, difficulty)
3. Profile retrieval: GET /api/v1/adaptive/profile
4. Session creation & answer key stripping: POST /api/v1/adaptive/session
5. Server-side quiz evaluation & scoring: POST /api/v1/adaptive/session/{id}/quiz/submit
6. Level progression and student profile persistence
7. Progress history: GET /api/v1/adaptive/progress
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from ai_module.generator import calculate_next_level, generate_adaptive_content
from app.db.session import init_db
from main import app


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        email = f"student_{uuid.uuid4().hex[:8]}@example.com"
        await c.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "full_name": "Test Student"},
        )
        login = await c.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Password123!"},
        )
        token = login.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ── 1. Unit Tests for Adaptive Logic ──────────────────────────────────────────

class TestCalculateNextLevel:
    """
    Test calculate_next_level against INTEGRATION_CONTRACT.md rules:
    - Score >= 80% promotes one level.
    - Score < 50% demotes one level.
    - Score from 50% to below 80% keeps the current level.
    - Beginner cannot go below Beginner.
    - Advanced cannot go above Advanced.
    - Returned values match exact capitalization: 'Beginner', 'Intermediate', 'Advanced'.
    - Boundary scores: 49, 50, 79, 80.
    - Invalid scores and invalid levels raise ValueError.
    """

    @pytest.mark.parametrize(
        "current_level,score,expected",
        [
            # Beginner boundaries
            ("Beginner", 49, "Beginner"),        # < 50% demote clamped at Beginner
            ("Beginner", 49.9, "Beginner"),      # < 50%
            ("Beginner", 50, "Beginner"),        # 50% to < 80% retain
            ("Beginner", 79, "Beginner"),        # 50% to < 80% retain
            ("Beginner", 79.9, "Beginner"),      # < 80%
            ("Beginner", 80, "Intermediate"),    # >= 80% promote
            ("Beginner", 100, "Intermediate"),   # >= 80% promote

            # Intermediate boundaries
            ("Intermediate", 49, "Beginner"),        # < 50% demote
            ("Intermediate", 49.9, "Beginner"),      # < 50% demote
            ("Intermediate", 50, "Intermediate"),    # 50% to < 80% retain
            ("Intermediate", 79, "Intermediate"),    # 50% to < 80% retain
            ("Intermediate", 79.9, "Intermediate"),  # < 80% retain
            ("Intermediate", 80, "Advanced"),        # >= 80% promote
            ("Intermediate", 100, "Advanced"),       # >= 80% promote

            # Advanced boundaries
            ("Advanced", 49, "Intermediate"),    # < 50% demote
            ("Advanced", 49.9, "Intermediate"),  # < 50% demote
            ("Advanced", 50, "Advanced"),        # 50% to < 80% retain
            ("Advanced", 79, "Advanced"),        # 50% to < 80% retain
            ("Advanced", 79.9, "Advanced"),      # < 80% retain
            ("Advanced", 80, "Advanced"),        # >= 80% promote clamped at Advanced
            ("Advanced", 100, "Advanced"),       # >= 80% promote clamped at Advanced
        ],
    )
    def test_boundary_scores_and_levels(self, current_level: str, score: float, expected: str):
        result = calculate_next_level(current_level, score)
        assert result == expected
        # Ensure returned level value matches exact contract capitalization
        assert result in ("Beginner", "Intermediate", "Advanced")

    @pytest.mark.parametrize(
        "input_level,score,expected",
        [
            ("beginner", 80, "Intermediate"),
            ("BEGINNER", 49, "Beginner"),
            ("bEgInNeR", 50, "Beginner"),
            ("intermediate", 80, "Advanced"),
            ("INTERMEDIATE", 49, "Beginner"),
            ("advanced", 49, "Intermediate"),
            ("ADVANCED", 80, "Advanced"),
        ],
    )
    def test_exact_contract_capitalization_returned_regardless_of_input_casing(
        self, input_level: str, score: float, expected: str
    ):
        result = calculate_next_level(input_level, score)
        assert result == expected
        assert result in ("Beginner", "Intermediate", "Advanced")

    @pytest.mark.parametrize(
        "invalid_score",
        [-1, -0.01, -50, 100.1, 101, 150, "eighty", "abc", None, [], {}, True, False],
    )
    def test_invalid_scores_raise_value_error(self, invalid_score):
        with pytest.raises(ValueError):
            calculate_next_level("Beginner", invalid_score)

    @pytest.mark.parametrize(
        "invalid_level",
        ["expert", "master", "novice", "", "   ", "random", "123", None, 123, True, []],
    )
    def test_invalid_levels_raise_value_error(self, invalid_level):
        with pytest.raises(ValueError):
            calculate_next_level(invalid_level, 80)


class TestGenerateAdaptiveContentFunction:
    async def test_generates_notes_and_quiz(self):
        result = await generate_adaptive_content(
            topic="Binary Search Trees",
            difficulty="intermediate",
        )
        assert result["topic"] == "Binary Search Trees"
        assert result["difficulty"] == "intermediate"
        assert "lesson" in result
        assert "sections" in result["lesson"]
        assert "quiz" in result
        assert "questions" in result["quiz"]
        assert len(result["quiz"]["questions"]) >= 5


# ── 2. Integration Tests for Endpoints ────────────────────────────────────────

class TestAdaptiveEndpoints:
    async def test_get_profile(self, client: AsyncClient):
        resp = await client.get("/api/v1/adaptive/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_level"] == "Beginner"
        assert data["total_sessions"] == 0
        assert data["quizzes_completed"] == 0
        assert data["average_score"] == 0.0

    async def test_create_session_strips_answer_key(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Data Structures", "difficulty": "Beginner"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["topic"] == "Data Structures"
        assert data["difficulty"] == "Beginner"
        assert "lesson" in data
        assert "quiz" in data
        assert len(data["quiz"]) >= 1

        # CRITICAL SECURITY VERIFICATION:
        # Client MUST NOT receive correct_label or explanation in questions!
        for q in data["quiz"]:
            assert "correct_label" not in q
            assert "explanation" not in q
            assert "question" in q
            assert "options" in q

    async def test_submit_quiz_evaluates_server_side_and_advances_level(
        self, client: AsyncClient
    ):
        # 1. Start a session
        sess_resp = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Python Generators", "difficulty": "Beginner"},
        )
        assert sess_resp.status_code == 201
        session_id = sess_resp.json()["session_id"]
        questions = sess_resp.json()["quiz"]

        # 2. In MockProvider, correct answer is "A"
        # Submit all "A"s to get 100%
        answers = [
            {"question_index": q["index"], "selected_label": "A"}
            for q in questions
        ]

        sub_resp = await client.post(
            f"/api/v1/adaptive/session/{session_id}/quiz/submit",
            json={"answers": answers},
        )
        assert sub_resp.status_code == 200
        result = sub_resp.json()

        # 3. Verify server evaluation & scoring formula
        assert result["session_id"] == session_id
        assert result["total_questions"] == len(questions)
        assert result["correct_count"] == len(questions)
        assert result["score_percentage"] == 100.0
        assert result["previous_level"] == "Beginner"
        assert result["new_level"] == "Intermediate"
        assert result["level_changed"] is True
        assert len(result["details"]) == len(questions)

        # 4. Verify student profile updated to Intermediate and persisted
        prof_resp = await client.get("/api/v1/adaptive/profile")
        prof_data = prof_resp.json()
        assert prof_data["current_level"] == "Intermediate"
        assert prof_data["quizzes_completed"] == 1
        assert prof_data["average_score"] == 100.0

    async def test_submit_quiz_evaluates_server_side_and_demotes_level(
        self, client: AsyncClient
    ):
        # 1. Promote to Intermediate first
        sess_1 = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Initial Session", "difficulty": "Beginner"},
        )
        s1_id = sess_1.json()["session_id"]
        q1_list = sess_1.json()["quiz"]
        # Score 100% to promote
        await client.post(
            f"/api/v1/adaptive/session/{s1_id}/quiz/submit",
            json={"answers": [{"question_index": q["index"], "selected_label": "A"} for q in q1_list]},
        )
        prof = (await client.get("/api/v1/adaptive/profile")).json()
        assert prof["current_level"] == "Intermediate"

        # 2. Start a session at Intermediate level
        sess_2 = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Advanced Algorithms", "difficulty": "Intermediate"},
        )
        assert sess_2.status_code == 201
        s2_id = sess_2.json()["session_id"]
        q2_list = sess_2.json()["quiz"]

        # 3. Score 0% (< 50%) by submitting wrong answers
        sub_resp = await client.post(
            f"/api/v1/adaptive/session/{s2_id}/quiz/submit",
            json={"answers": [{"question_index": q["index"], "selected_label": "B"} for q in q2_list]},
        )
        assert sub_resp.status_code == 200
        result = sub_resp.json()

        # 4. Verify demotion calculation & DB persistence
        assert result["correct_count"] == 0
        assert result["score_percentage"] == 0.0
        assert result["previous_level"] == "Intermediate"
        assert result["new_level"] == "Beginner"
        assert result["level_changed"] is True

        prof_after = (await client.get("/api/v1/adaptive/profile")).json()
        assert prof_after["current_level"] == "Beginner"

    async def test_beginner_cannot_go_below_beginner_on_server(
        self, client: AsyncClient
    ):
        # Student profile starts at Beginner
        sess = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Basics", "difficulty": "Beginner"},
        )
        sess_id = sess.json()["session_id"]
        q_list = sess.json()["quiz"]

        # Score 0% (< 50%)
        sub_resp = await client.post(
            f"/api/v1/adaptive/session/{sess_id}/quiz/submit",
            json={"answers": [{"question_index": q["index"], "selected_label": "B"} for q in q_list]},
        )
        assert sub_resp.status_code == 200
        result = sub_resp.json()
        assert result["previous_level"] == "Beginner"
        assert result["new_level"] == "Beginner"
        assert result["level_changed"] is False

        prof = (await client.get("/api/v1/adaptive/profile")).json()
        assert prof["current_level"] == "Beginner"

    async def test_quiz_score_between_50_and_80_retains_level_on_server(
        self, client: AsyncClient
    ):
        sess = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Retain Test", "difficulty": "Beginner"},
        )
        sess_id = sess.json()["session_id"]
        q_list = sess.json()["quiz"]
        total = len(q_list)

        # Answer 3 correctly out of 5 (60.0%, which is >= 50% and < 80%)
        answers = []
        for idx, q in enumerate(q_list):
            label = "A" if idx < 3 else "B"
            answers.append({"question_index": q["index"], "selected_label": label})

        sub_resp = await client.post(
            f"/api/v1/adaptive/session/{sess_id}/quiz/submit",
            json={"answers": answers},
        )
        assert sub_resp.status_code == 200
        result = sub_resp.json()
        expected_score = round((3 / total) * 100.0, 2)
        assert result["score_percentage"] == expected_score
        assert result["previous_level"] == "Beginner"
        assert result["new_level"] == "Beginner"
        assert result["level_changed"] is False

    async def test_cannot_resubmit_completed_quiz(self, client: AsyncClient):
        sess_resp = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Recursion", "difficulty": "Beginner"},
        )
        session_id = sess_resp.json()["session_id"]

        # First submit
        await client.post(
            f"/api/v1/adaptive/session/{session_id}/quiz/submit",
            json={"answers": [{"question_index": 0, "selected_label": "A"}]},
        )

        # Second submit should fail with 400
        second_resp = await client.post(
            f"/api/v1/adaptive/session/{session_id}/quiz/submit",
            json={"answers": [{"question_index": 0, "selected_label": "A"}]},
        )
        assert second_resp.status_code == 400

    async def test_submit_nonexistent_session_returns_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/adaptive/session/{fake_id}/quiz/submit",
            json={"answers": [{"question_index": 0, "selected_label": "A"}]},
        )
        assert resp.status_code == 404

    async def test_progress_history(self, client: AsyncClient):
        # Create and submit a session
        sess_resp = await client.post(
            "/api/v1/adaptive/session",
            json={"topic": "Sorting Algorithms", "difficulty": "Beginner"},
        )
        session_id = sess_resp.json()["session_id"]
        await client.post(
            f"/api/v1/adaptive/session/{session_id}/quiz/submit",
            json={"answers": [{"question_index": 0, "selected_label": "A"}]},
        )

        # Fetch progress history
        prog_resp = await client.get("/api/v1/adaptive/progress")
        assert prog_resp.status_code == 200
        history = prog_resp.json()
        assert isinstance(history, list)
        assert len(history) >= 1
        assert "score_percentage" in history[0]
        assert "topic" in history[0]
        assert "new_level" in history[0]
