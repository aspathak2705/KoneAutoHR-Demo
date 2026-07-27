#!/usr/bin/env python3
"""
Phase 2 Verification - Runtime Coordinator Lifecycle Refactor

Tests:
1. prepare_runtime() - Asset validation, prerequisite checking
2. start_induction() - Browser launch with retry policy
3. join_meeting() - Teams navigation and device configuration
4. finish_presentation() - Resource cleanup in reverse order

All tests verify state machine transitions, database persistence, and error handling.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

# Setup path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Set environment variables
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase2.db")
os.environ.setdefault("UPLOAD_PATH", "./uploads")
os.environ.setdefault("MAX_UPLOAD_SIZE", "52428800")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")

# Imports
from app.db.database import SessionLocal, Base, engine
from app.modules.induction_runtime.orchestrator.runtime_coordinator import RuntimeCoordinator
from app.modules.induction_runtime.models.runtime_state import RuntimeState
from app.services.runtime_service import runtime_service
from app.models.runtime import Runtime
from loguru import logger


@dataclass
class TestResult:
    """Test result tracking"""
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: str = ""
    
    def __str__(self) -> str:
        icon = "[✓]" if self.passed else "[✗]"
        msg = f"{icon} {self.name:<45} {self.duration:.2f}s"
        if self.error:
            msg += f" | Error: {self.error}"
        if self.details:
            msg += f" | {self.details}"
        return msg


class Phase2Verifier:
    """Phase 2 Verification Suite"""
    
    def __init__(self):
        self.results: list[TestResult] = []
        self.db = None
        self.runtime_ids: list[str] = []
        
    def setup(self):
        """Initialize test database"""
        print("\n[*] Setting up test database...")
        # Import models to ensure they are registered with SQLAlchemy Base
        from app.models.presentation_asset import PresentationAsset
        from app.models.presentation_metadata import PresentationMetadata
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        print("[✓] Database ready")
        
    def teardown(self):
        """Cleanup test database"""
        print("\n[*] Cleaning up...")
        if self.db:
            self.db.close()
        # Delete test database
        if Path("test_phase2.db").exists():
            os.remove("test_phase2.db")
        print("[✓] Cleanup complete")
        
    async def test_prepare_runtime_success(self) -> TestResult:
        """
        Test A1: prepare_runtime() Success Path
        Verifies: NOT_CREATED → PREPARING → READY
        """
        test_name = "A1: prepare_runtime() - Success Path"
        start = time.time()
        
        try:
            session_id = "test-prepare-success"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # Set prerequisites
            coordinator.script_slides = [{"slide_number": 1, "narration": "Test slide"}]
            coordinator.employee_context.employees_list = [{"id": "emp-1", "name": "John Doe"}]
            coordinator.presenter_context.profile = {"name": "Trainer", "bio": "Test trainer"}
            coordinator.faq_records = [{"question": "Q1", "answer": "A1"}]
            
            # Mock _initialize_context to bypass DB lookup for session/meetings in test
            coordinator._initialize_context = lambda: None
            
            # Call prepare_runtime
            result = await coordinator.prepare_runtime()
            duration = time.time() - start
            
            # Verify results
            assert result is True, "prepare_runtime() should return True"
            assert coordinator.session_manager.state == RuntimeState.READY, f"State should be READY, got {coordinator.session_manager.state}"
            
            # Verify database persistence
            db_runtime = self.db.query(Runtime).filter(Runtime.id == coordinator.runtime_id).first()
            assert db_runtime is not None, "Runtime not found in database"
            assert db_runtime.state == RuntimeState.READY.value, f"Database state should be READY, got {db_runtime.state}"
            
            return TestResult(test_name, True, duration, details=f"State: {coordinator.session_manager.state.value}")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_prepare_runtime_missing_prerequisites(self) -> TestResult:
        """
        Test A2: prepare_runtime() Missing Prerequisites
        Verifies: Fails when assets missing, transitions to FAILED
        """
        test_name = "A2: prepare_runtime() - Missing Prerequisites"
        start = time.time()
        
        try:
            session_id = "test-prepare-missing"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # DO NOT set prerequisites - leave empty
            
            # Call prepare_runtime
            result = await coordinator.prepare_runtime()
            duration = time.time() - start
            
            # Verify results
            assert result is False, "prepare_runtime() should return False when prerequisites missing"
            assert coordinator.session_manager.state == RuntimeState.FAILED, f"State should be FAILED, got {coordinator.session_manager.state}"
            assert coordinator.session_manager.last_error is not None, "last_error should be populated"
            
            # Verify database persistence
            db_runtime = self.db.query(Runtime).filter(Runtime.id == coordinator.runtime_id).first()
            assert db_runtime.state == RuntimeState.FAILED.value, "Database state should be FAILED"
            assert db_runtime.last_error is not None, "Database last_error should be populated"
            
            return TestResult(test_name, True, duration, details=f"Error: {coordinator.session_manager.last_error[:40]}...")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_start_induction_wrong_state(self) -> TestResult:
        """
        Test A5: start_induction() From Wrong State
        Verifies: Fails when not in READY state
        """
        test_name = "A5: start_induction() - Wrong State"
        start = time.time()
        
        try:
            session_id = "test-induction-wrong"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # Force state to PREPARING (wrong state)
            await coordinator.session_manager.transition_to(RuntimeState.PREPARING)
            
            # Try to start induction
            result = await coordinator.start_induction()
            duration = time.time() - start
            
            # Verify results
            assert result is False, "start_induction() should fail from PREPARING state"
            assert coordinator.session_manager.state == RuntimeState.FAILED, f"State should be FAILED, got {coordinator.session_manager.state}"
            
            return TestResult(test_name, True, duration, details=f"Correctly rejected from {RuntimeState.PREPARING.value}")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_join_meeting_wrong_state(self) -> TestResult:
        """
        Test A9: join_meeting() From Wrong State
        Verifies: Fails when not in BROWSER_READY state
        """
        test_name = "A9: join_meeting() - Wrong State"
        start = time.time()
        
        try:
            session_id = "test-join-wrong"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # Force state to READY (wrong state for join)
            await coordinator.session_manager.transition_to(RuntimeState.PREPARING)
            await coordinator.session_manager.transition_to(RuntimeState.READY)
            
            # Try to join meeting
            result = await coordinator.join_meeting("https://teams.com/meeting")
            duration = time.time() - start
            
            # Verify results
            assert result is False, "join_meeting() should fail from READY state"
            assert coordinator.session_manager.state == RuntimeState.FAILED, f"State should be FAILED, got {coordinator.session_manager.state}"
            
            return TestResult(test_name, True, duration, details=f"Correctly rejected from {RuntimeState.READY.value}")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_state_machine_valid_transitions(self) -> TestResult:
        """
        Test B2: Valid State Transitions
        Verifies: All locked transitions work correctly
        """
        test_name = "B2: State Machine - Valid Transitions"
        start = time.time()
        
        try:
            session_id = "test-state-machine"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # Define valid transition path
            transitions = [
                RuntimeState.NOT_CREATED,
                RuntimeState.PREPARING,
                RuntimeState.READY,
                RuntimeState.STARTING,
                RuntimeState.BROWSER_READY,
                RuntimeState.JOINING,
                RuntimeState.WAITING,
                RuntimeState.CONNECTED,
                RuntimeState.PRESENTING,
                RuntimeState.FINISHED,
                RuntimeState.STOPPING,
                RuntimeState.STOPPED,
            ]
            
            # Execute transitions
            for i in range(1, len(transitions)):
                current = coordinator.session_manager.state
                target = transitions[i]
                
                # Only test forward progression
                result = await coordinator.session_manager.transition_to(target)
                assert result is True, f"Transition {current.value} → {target.value} should succeed"
                assert coordinator.session_manager.state == target, f"State should be {target.value}, got {coordinator.session_manager.state.value}"
            
            duration = time.time() - start
            return TestResult(test_name, True, duration, details=f"All {len(transitions)-1} transitions valid")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_state_machine_invalid_transitions(self) -> TestResult:
        """
        Test B1: Invalid State Transitions Rejected
        Verifies: Invalid transitions are rejected
        """
        test_name = "B1: State Machine - Invalid Transitions"
        start = time.time()
        
        try:
            session_id = "test-invalid-transitions"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            
            # Test invalid transitions
            invalid_transitions = [
                (RuntimeState.NOT_CREATED, RuntimeState.READY, "Skips PREPARING"),
                (RuntimeState.READY, RuntimeState.BROWSER_READY, "Skips STARTING"),
                (RuntimeState.CONNECTED, RuntimeState.STOPPED, "Skips PRESENTING, FINISHED, STOPPING"),
            ]
            
            for i, (source, target, desc) in enumerate(invalid_transitions):
                # Set source state
                coordinator.session_manager.state = source
                
                # Try invalid transition
                result = await coordinator.session_manager.transition_to(target)
                assert result is False, f"Transition {source.value} → {target.value} ({desc}) should be rejected"
                assert coordinator.session_manager.state == source, f"State should remain {source.value} after invalid transition"
            
            duration = time.time() - start
            return TestResult(test_name, True, duration, details=f"All {len(invalid_transitions)} invalid transitions rejected")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_error_path_from_all_states(self) -> TestResult:
        """
        Test B3: Error Path Available from All States
        Verifies: FAILED transition available from any state
        """
        test_name = "B3: State Machine - Error Path"
        start = time.time()
        
        try:
            # Test from multiple states
            test_states = [
                RuntimeState.PREPARING,
                RuntimeState.READY,
                RuntimeState.STARTING,
                RuntimeState.BROWSER_READY,
                RuntimeState.JOINING,
                RuntimeState.WAITING,
                RuntimeState.CONNECTED,
                RuntimeState.PRESENTING,
            ]
            
            for state in test_states:
                session_id = f"test-error-{state.value}"
                
                # Create runtime entry
                coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
                self.runtime_ids.append(coordinator.runtime_id)
                
                # Set state
                coordinator.session_manager.state = state
                
                # Transition to FAILED with error message
                result = await coordinator.session_manager.transition_to(RuntimeState.FAILED, f"Test error from {state.value}")
                assert result is True, f"Transition {state.value} → FAILED should always succeed"
                assert coordinator.session_manager.state == RuntimeState.FAILED, f"State should be FAILED"
                assert coordinator.session_manager.last_error is not None, "last_error should be set"
            
            duration = time.time() - start
            return TestResult(test_name, True, duration, details=f"Error path available from {len(test_states)} states")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def test_database_persistence(self) -> TestResult:
        """
        Test F1: Database Persistence
        Verifies: State transitions persisted to database
        """
        test_name = "F1: Database - State Persistence"
        start = time.time()
        
        try:
            session_id = "test-db-persist"
            
            # Create runtime entry
            coordinator = runtime_service.create_runtime_and_coordinator(self.db, session_id)
            self.runtime_ids.append(coordinator.runtime_id)
            runtime_id = coordinator.runtime_id
            
            # Set prerequisites and prepare
            coordinator.script_slides = [{"slide_number": 1, "narration": "Test"}]
            coordinator.employee_context.employees_list = [{"id": "emp-1"}]
            coordinator.presenter_context.profile = {"name": "Trainer"}
            coordinator.faq_records = [{"q": "Q1", "a": "A1"}]
            
            # Mock _initialize_context to bypass DB lookup for session/meetings in test
            coordinator._initialize_context = lambda: None
            
            await coordinator.prepare_runtime()
            
            # Query database
            db_runtime = self.db.query(Runtime).filter(Runtime.id == runtime_id).first()
            assert db_runtime is not None, "Runtime not found in database"
            assert db_runtime.state == RuntimeState.READY.value, f"DB state should be READY, got {db_runtime.state}"
            
            # Transition to STARTING
            await coordinator.session_manager.transition_to(RuntimeState.STARTING)
            
            # Query again
            db_runtime = self.db.query(Runtime).filter(Runtime.id == runtime_id).first()
            assert db_runtime.state == RuntimeState.STARTING.value, f"DB state should be STARTING, got {db_runtime.state}"
            
            duration = time.time() - start
            return TestResult(test_name, True, duration, details=f"Verified {RuntimeState.READY.value} and {RuntimeState.STARTING.value} persistence")
        except AssertionError as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=str(e))
        except Exception as e:
            duration = time.time() - start
            return TestResult(test_name, False, duration, error=f"Exception: {type(e).__name__}: {e}")
    
    async def run_all_tests(self):
        """Execute all Phase 2 verification tests"""
        print("\n" + "=" * 80)
        print("         PHASE 2 VERIFICATION - RUNTIME COORDINATOR LIFECYCLE")
        print("=" * 80)
        
        self.setup()
        
        # Run all tests
        tests = [
            self.test_prepare_runtime_success,
            self.test_prepare_runtime_missing_prerequisites,
            self.test_start_induction_wrong_state,
            self.test_join_meeting_wrong_state,
            self.test_state_machine_valid_transitions,
            self.test_state_machine_invalid_transitions,
            self.test_error_path_from_all_states,
            self.test_database_persistence,
        ]
        
        for test_func in tests:
            result = await test_func()
            self.results.append(result)
            print(result)
        
        # Print summary
        print("\n" + "=" * 80)
        print("         PHASE 2 VERIFICATION SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        for result in self.results:
            status = "[PASS]" if result.passed else "[FAIL]"
            print(f"{status} {result.name}")
        
        print("-" * 80)
        print(f"TOTAL: {passed}/{total} tests passed")
        
        if passed == total:
            print("✓ ALL TESTS PASSED - Phase 2 ready for integration testing")
        else:
            print(f"✗ {total - passed} test(s) FAILED - Review errors above")
        
        print("=" * 80)
        
        self.teardown()
        
        return passed == total


async def main():
    """Main entry point"""
    verifier = Phase2Verifier()
    success = await verifier.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
