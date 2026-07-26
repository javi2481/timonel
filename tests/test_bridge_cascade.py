"""Tests de cascada por evidencia (política pura + selección de oleadas).

Ejecutar desde la raíz del repo:

    PYTHONPATH=. python3 tests/test_bridge_cascade.py
"""

from __future__ import annotations

import unittest

from bridge.cascade import (
    CascadeConfig,
    DEPENDENT_CAP_NAMES,
    ObjectsEvidenceState,
    classify_objects_evidence,
    decide_dependent_caps,
    dependent_names_from_decision,
    has_face_evidence,
    has_person_evidence,
    needs_open_vocab_second_opinion,
    wave1_capability_names,
)


class ClassifyObjectsEvidenceTests(unittest.TestCase):
    def test_disabled_when_objects_not_active(self) -> None:
        state = classify_objects_evidence(
            [{"label": "dog", "score": 0.9}],
            objects_active=False,
            low_score=0.35,
        )
        self.assertEqual(state, ObjectsEvidenceState.DISABLED)

    def test_failed_on_none(self) -> None:
        state = classify_objects_evidence(
            None, objects_active=True, low_score=0.35
        )
        self.assertEqual(state, ObjectsEvidenceState.FAILED)

    def test_empty_on_empty_list(self) -> None:
        state = classify_objects_evidence(
            [], objects_active=True, low_score=0.35
        )
        self.assertEqual(state, ObjectsEvidenceState.EMPTY)

    def test_low_confidence_when_max_below_threshold(self) -> None:
        state = classify_objects_evidence(
            [{"label": "dog", "score": 0.2}, {"label": "cat", "score": 0.1}],
            objects_active=True,
            low_score=0.35,
        )
        self.assertEqual(state, ObjectsEvidenceState.LOW_CONFIDENCE)

    def test_hits_when_max_at_or_above_threshold(self) -> None:
        state = classify_objects_evidence(
            [{"label": "dog", "score": 0.2}, {"label": "cat", "score": 0.35}],
            objects_active=True,
            low_score=0.35,
        )
        self.assertEqual(state, ObjectsEvidenceState.HITS)

    def test_malformed_scores_ignored_for_max(self) -> None:
        state = classify_objects_evidence(
            [
                {"label": "dog", "score": "bad"},
                {"label": "cat"},  # missing score
                {"label": "bird", "score": 0.9},
            ],
            objects_active=True,
            low_score=0.35,
        )
        self.assertEqual(state, ObjectsEvidenceState.HITS)

    def test_all_malformed_scores_are_low_confidence(self) -> None:
        state = classify_objects_evidence(
            [{"label": "dog"}, {"label": "cat", "score": "x"}],
            objects_active=True,
            low_score=0.35,
        )
        self.assertEqual(state, ObjectsEvidenceState.LOW_CONFIDENCE)

    def test_disabled_does_not_use_object_scores_for_open_vocab(self) -> None:
        """objects off → DISABLED; never treat as empty/failed for OV."""
        self.assertFalse(
            needs_open_vocab_second_opinion(ObjectsEvidenceState.DISABLED)
        )
        self.assertTrue(
            needs_open_vocab_second_opinion(ObjectsEvidenceState.EMPTY)
        )
        self.assertTrue(
            needs_open_vocab_second_opinion(ObjectsEvidenceState.FAILED)
        )
        self.assertTrue(
            needs_open_vocab_second_opinion(ObjectsEvidenceState.LOW_CONFIDENCE)
        )
        self.assertFalse(
            needs_open_vocab_second_opinion(ObjectsEvidenceState.HITS)
        )


class PersonFaceEvidenceTests(unittest.TestCase):
    def test_person_label_case_insensitive(self) -> None:
        self.assertTrue(
            has_person_evidence([{"label": "Person", "score": 0.5}])
        )

    def test_person_without_score_counts(self) -> None:
        self.assertTrue(has_person_evidence([{"label": "person"}]))

    def test_no_person(self) -> None:
        self.assertFalse(
            has_person_evidence([{"label": "car", "score": 0.9}])
        )

    def test_face_empty_list(self) -> None:
        self.assertFalse(has_face_evidence([]))
        self.assertFalse(has_face_evidence(None))

    def test_face_hits(self) -> None:
        self.assertTrue(has_face_evidence([{"label": "face", "score": 0.8}]))


class DecideDependentCapsTests(unittest.TestCase):
    def _cfg(self, enabled: bool = True, low: float = 0.35) -> CascadeConfig:
        return CascadeConfig(enabled=enabled, object_low_score=low)

    def test_person_triggers_pedestrians(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[{"label": "person", "score": 0.7}],
            faces_raw=None,
            open_vocab_in_gather=False,
            pedestrians_in_gather=True,
            face_id_in_gather=False,
        )
        self.assertTrue(d.run_pedestrians)
        self.assertFalse(d.run_face_id)
        self.assertFalse(d.run_open_vocab)
        self.assertIn("pedestrians", dependent_names_from_decision(d))

    def test_no_person_skips_pedestrians(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[{"label": "dog", "score": 0.9}],
            faces_raw=[],
            open_vocab_in_gather=False,
            pedestrians_in_gather=True,
            face_id_in_gather=False,
        )
        self.assertFalse(d.run_pedestrians)

    def test_face_triggers_face_id(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[{"label": "person", "score": 0.8}],
            faces_raw=[{"label": "face", "score": 0.9}],
            open_vocab_in_gather=False,
            pedestrians_in_gather=True,
            face_id_in_gather=True,
        )
        self.assertTrue(d.run_face_id)

    def test_no_face_skips_face_id(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[{"label": "person", "score": 0.8}],
            faces_raw=[],
            open_vocab_in_gather=False,
            pedestrians_in_gather=True,
            face_id_in_gather=True,
        )
        self.assertFalse(d.run_face_id)

    def test_objects_empty_triggers_open_vocab(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[],
            faces_raw=None,
            open_vocab_in_gather=True,
            pedestrians_in_gather=False,
            face_id_in_gather=False,
        )
        self.assertTrue(d.run_open_vocab)
        self.assertEqual(d.objects_state, ObjectsEvidenceState.EMPTY)

    def test_objects_hits_skip_open_vocab(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[{"label": "dog", "score": 0.9}],
            faces_raw=None,
            open_vocab_in_gather=True,
            pedestrians_in_gather=False,
            face_id_in_gather=False,
        )
        self.assertFalse(d.run_open_vocab)

    def test_objects_disabled_does_not_trigger_open_vocab(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=False,
            object_raw=None,
            faces_raw=None,
            open_vocab_in_gather=True,
            pedestrians_in_gather=False,
            face_id_in_gather=False,
        )
        self.assertEqual(d.objects_state, ObjectsEvidenceState.DISABLED)
        self.assertFalse(d.run_open_vocab)

    def test_inactive_open_vocab_not_run(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(),
            objects_active=True,
            object_raw=[],
            faces_raw=None,
            open_vocab_in_gather=False,
            pedestrians_in_gather=False,
            face_id_in_gather=False,
        )
        self.assertFalse(d.run_open_vocab)

    def test_cascade_disabled_runs_nothing_dependent(self) -> None:
        d = decide_dependent_caps(
            config=self._cfg(enabled=False),
            objects_active=True,
            object_raw=[],
            faces_raw=[{"label": "face"}],
            open_vocab_in_gather=True,
            pedestrians_in_gather=True,
            face_id_in_gather=True,
        )
        self.assertFalse(d.run_pedestrians)
        self.assertFalse(d.run_face_id)
        self.assertFalse(d.run_open_vocab)
        self.assertIn("cascade=disabled", d.reasons)

    def test_scores_not_compared_across_models(self) -> None:
        """Face score alto no cuenta como objects HITS; OV usa solo COCO."""
        d = decide_dependent_caps(
            config=self._cfg(low=0.35),
            objects_active=True,
            object_raw=[{"label": "dog", "score": 0.1}],  # low COCO
            faces_raw=[{"label": "face", "score": 0.99}],  # other model
            open_vocab_in_gather=True,
            pedestrians_in_gather=False,
            face_id_in_gather=True,
        )
        self.assertEqual(d.objects_state, ObjectsEvidenceState.LOW_CONFIDENCE)
        self.assertTrue(d.run_open_vocab)
        self.assertTrue(d.run_face_id)


class WaveSplitTests(unittest.TestCase):
    def test_wave1_excludes_dependents_when_enabled(self) -> None:
        eligible = {
            "vehicles",
            "objects",
            "faces",
            "pedestrians",
            "face_id",
            "open_vocab",
            "signs",
        }
        w1 = wave1_capability_names(eligible, cascade_enabled=True)
        self.assertEqual(w1 & DEPENDENT_CAP_NAMES, set())
        self.assertIn("vehicles", w1)
        self.assertIn("faces", w1)
        self.assertIn("signs", w1)

    def test_wave1_keeps_all_when_disabled(self) -> None:
        eligible = {"vehicles", "pedestrians", "open_vocab"}
        w1 = wave1_capability_names(eligible, cascade_enabled=False)
        self.assertEqual(w1, eligible)


class GatherCapabilitiesAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_gather_preserves_names_and_order_keys(self) -> None:
        from detection.registry import Capability
        from bridge.main import gather_capabilities

        calls: list[str] = []

        async def make_infer(name: str):
            async def _infer(client, jpeg, **kwargs):
                calls.append(name)
                return [{"label": name, "score": 0.5}]

            return _infer

        caps = []
        for n in ("faces", "signs"):
            infer = await make_infer(n)
            caps.append(Capability(n, infer, "extend_scaled"))

        class _Client:
            pass

        by_name = await gather_capabilities(_Client(), caps, b"jpeg", (100, 100))
        self.assertEqual(set(by_name.keys()), {"faces", "signs"})
        self.assertEqual(by_name["faces"][0]["label"], "faces")
        self.assertEqual(sorted(calls), ["faces", "signs"])

    async def test_empty_caps_returns_empty_dict(self) -> None:
        from bridge.main import gather_capabilities

        class _Client:
            pass

        self.assertEqual(
            await gather_capabilities(_Client(), [], b"x", (1, 1)), {}
        )


if __name__ == "__main__":
    unittest.main()
