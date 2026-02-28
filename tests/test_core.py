"""
Unit tests for core business logic.

Run with pytest (recommended):
    pytest tests/ -v
    pytest tests/test_core.py -v

Run directly (manual):
    python -m tests.test_core      (from project root)
"""
import sys
import os

# Add project root to path if running directly
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Make pytest optional - only needed for pytest runner
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from app.services.escrow_service import calculate_booking_fees


class TestEscrowFeeCalculation:
    """Test the platform fee calculation logic."""

    def test_standard_10_percent_fee(self):
        fees = calculate_booking_fees(total_amount=100.0, fee_percent=10.0)
        assert fees["client_fee"] == 10.0
        assert fees["worker_fee"] == 10.0
        assert fees["worker_payout"] == 90.0
        assert fees["client_total"] == 110.0

    def test_platform_earns_both_fees(self):
        fees = calculate_booking_fees(total_amount=200.0, fee_percent=10.0)
        platform_revenue = fees["client_fee"] + fees["worker_fee"]
        assert platform_revenue == 40.0

    def test_zero_fee(self):
        fees = calculate_booking_fees(total_amount=100.0, fee_percent=0.0)
        assert fees["client_fee"] == 0.0
        assert fees["worker_fee"] == 0.0
        assert fees["worker_payout"] == 100.0
        assert fees["client_total"] == 100.0

    def test_five_percent_fee(self):
        fees = calculate_booking_fees(total_amount=200.0, fee_percent=5.0)
        assert fees["client_fee"] == 10.0
        assert fees["worker_fee"] == 10.0
        assert fees["worker_payout"] == 190.0
        assert fees["client_total"] == 210.0

    def test_decimal_amounts(self):
        # 3 hours at 45.50/hr = 136.50
        fees = calculate_booking_fees(total_amount=136.50, fee_percent=10.0)
        assert fees["client_fee"] == 13.65
        assert fees["worker_fee"] == 13.65
        assert round(fees["worker_payout"], 2) == 122.85
        assert round(fees["client_total"], 2) == 150.15

    def test_worker_payout_plus_worker_fee_equals_total(self):
        fees = calculate_booking_fees(total_amount=500.0, fee_percent=10.0)
        assert fees["worker_payout"] + fees["worker_fee"] == 500.0

    def test_client_total_minus_client_fee_equals_total(self):
        fees = calculate_booking_fees(total_amount=500.0, fee_percent=10.0)
        assert fees["client_total"] - fees["client_fee"] == 500.0

    def test_large_amounts(self):
        fees = calculate_booking_fees(total_amount=10000.0, fee_percent=10.0)
        assert fees["client_total"] == 11000.0
        assert fees["worker_payout"] == 9000.0


class TestPasswordHashing:
    """Test password utilities."""

    def test_hash_and_verify(self):
        from app.services.auth_service import hash_password, verify_password
        password = "testpassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        from app.services.auth_service import hash_password, verify_password
        hashed = hash_password("correctpassword")
        assert not verify_password("wrongpassword", hashed)


class TestJWTToken:
    """Test JWT token creation and decoding."""

    def test_create_and_decode_token(self):
        from app.services.auth_service import create_access_token, decode_token
        token = create_access_token({"sub": "42", "role": "client"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["role"] == "client"

    def test_invalid_token_returns_none(self):
        from app.services.auth_service import decode_token
        result = decode_token("this.is.not.a.valid.token")
        assert result is None

    def test_expired_token(self):
        from datetime import timedelta
        from app.services.auth_service import create_access_token, decode_token
        # Create token that expires in negative time (already expired)
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        result = decode_token(token)
        assert result is None


# --- Manual Test Runner ------------------------------------------------------
def run_all_tests():
    """
    Run all tests manually (for direct execution without pytest).
    This provides colored output and a summary.
    """
    print("\n" + "="*70)
    print(" 🧪 QATAR LABOR MARKETPLACE - TEST SUITE")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    errors = []
    
    # Test classes and their methods
    test_classes = [
        (TestEscrowFeeCalculation, "Escrow Fee Calculation"),
        (TestPasswordHashing, "Password Hashing"),
        (TestJWTToken, "JWT Token Management"),
    ]
    
    for test_class, class_name in test_classes:
        print(f"📦 {class_name}")
        print("-" * 70)
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        instance = test_class()
        
        for method_name in test_methods:
            test_method = getattr(instance, method_name)
            test_display_name = method_name.replace('_', ' ').replace('test ', '').title()
            
            try:
                test_method()
                print(f"   {test_display_name}")
                passed += 1
            except AssertionError as e:
                print(f"  ERROR: {test_display_name}")
                print(f"     ↳ Assertion failed: {e}")
                failed += 1
                errors.append((class_name, test_display_name, str(e)))
            except Exception as e:
                print(f"  💥 {test_display_name}")
                print(f"     ↳ Error: {e}")
                failed += 1
                errors.append((class_name, test_display_name, str(e)))
        
        print()
    
    # Summary
    print("="*70)
    print(f"  TEST RESULTS")
    print("="*70)
    print(f"   Passed:  {passed}")
    print(f"  ERROR: Failed:  {failed}")
    print(f"  📈 Total:   {passed + failed}")
    print(f"  🎯 Success Rate: {(passed / (passed + failed) * 100):.1f}%")
    print("="*70 + "\n")
    
    # Show errors if any
    if errors:
        print("ERROR: FAILED TESTS DETAIL:\n")
        for i, (class_name, test_name, error) in enumerate(errors, 1):
            print(f"{i}. {class_name} → {test_name}")
            print(f"   {error}\n")
    
    # Exit code (0 = success, 1 = failure)
    return 0 if failed == 0 else 1


def main():
    """
    Main entry point when running this file directly.
    Offers choice between manual runner and pytest.
    """
    if len(sys.argv) > 1 and sys.argv[1] == '--pytest':
        # Run with pytest if --pytest flag is provided
        if not PYTEST_AVAILABLE:
            print("\nERROR: pytest is not installed. Install with: pip install pytest")
            print("   Running with manual test runner instead...\n")
            sys.exit(run_all_tests())
        else:
            print("\n🔬 Running tests with pytest...\n")
            sys.exit(pytest.main([__file__, '-v', '--tb=short']))
    else:
        # Run manual test runner
        sys.exit(run_all_tests())


if __name__ == "__main__":
    main()
