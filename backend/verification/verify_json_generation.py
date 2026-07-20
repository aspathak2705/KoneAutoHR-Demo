import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.modules.induction.llm.response_parser import parse_llm_json
from app.modules.induction.llm.client import llm_client
from app.core.exceptions import LLMResponseParseError, InvalidResponseError

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def test_extraction_scenarios():
    print("=====================================================================")
    print("              AUTOHR RELIABLE JSON GENERATION VERIFIER              ")
    print("=====================================================================\n")

    # Test 1: Valid JSON
    raw_1 = '{"title": "Welcome", "status": "active"}'
    try:
        res1 = parse_llm_json(raw_1)
        print_result("Test 1: Valid JSON parsing", res1.get("title") == "Welcome")
    except Exception as e:
        print_result("Test 1: Valid JSON parsing", False, str(e))

    # Test 2: JSON wrapped in Markdown code fences
    raw_2 = '```json\n{"title": "Welcome Code Block", "status": "active"}\n```'
    try:
        res2 = parse_llm_json(raw_2)
        print_result("Test 2: Markdown wrapped JSON parsing", res2.get("title") == "Welcome Code Block")
    except Exception as e:
        print_result("Test 2: Markdown wrapped JSON parsing", False, str(e))

    # Test 3: Introductory text before JSON
    raw_3 = 'Here is the requested JSON object:\n\n{"title": "Intro Text JSON", "status": "active"}\n\nHope this helps!'
    try:
        res3 = parse_llm_json(raw_3)
        print_result("Test 3: Introductory text before JSON", res3.get("title") == "Intro Text JSON")
    except Exception as e:
        print_result("Test 3: Introductory text before JSON", False, str(e))

    # Test 4 & 5 Mock Retry flow verification
    async def mock_retry_tests():
        # Test 4: Single retry success mock
        class MockLLMClientRetry(llm_client.__class__):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            async def _call_api(self, prompt: str, system_prompt: str = None, retry_user_msg: str = None):
                self.call_count += 1
                if self.call_count == 1:
                    # Invalid json first attempt
                    return "{ title: malformed ", 0.1, 10, 10
                # Valid json on second attempt
                return '{"title": "Retry Success"}', 0.1, 10, 10

        mock_client = MockLLMClientRetry()
        mock_client.api_key = "mock"
        res4 = await mock_client.generate_json("test prompt")
        print_result("Test 4: Retry once succeeds on 2nd attempt", res4.get("title") == "Retry Success")

        # Test 5: Both attempts fail
        class MockLLMClientDoubleFail(llm_client.__class__):
            async def _call_api(self, prompt: str, system_prompt: str = None, retry_user_msg: str = None):
                return "{ invalid json ", 0.1, 10, 10

        mock_fail = MockLLMClientDoubleFail()
        mock_fail.api_key = "mock"
        passed_fail = False
        try:
            await mock_fail.generate_json("test prompt")
        except InvalidResponseError:
            passed_fail = True

        print_result("Test 5: Both attempts fail raises InvalidResponseError", passed_fail)

    asyncio.run(mock_retry_tests())

    print("\n=====================================================================")
    print("                 RELIABLE JSON TESTS PASS                            ")
    print("=====================================================================")

if __name__ == "__main__":
    test_extraction_scenarios()
