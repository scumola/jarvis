#!/bin/bash
# Test runner for all Jarvis demos
# Runs each demo and logs results

LOGDIR="demo_test_logs"
mkdir -p "$LOGDIR"

echo "======================================================================"
echo "JARVIS DEMO TEST SUITE"
echo "======================================================================"
echo "Testing all demos systematically..."
echo "Logs will be saved to: $LOGDIR/"
echo "======================================================================"
echo ""

# Function to run a demo
run_demo() {
    local demo_name="$1"
    local demo_path="$2"
    local input="$3"
    local logfile="$LOGDIR/${demo_name}.log"

    echo "──────────────────────────────────────────────────────────────────"
    echo "Testing: $demo_name"
    echo "──────────────────────────────────────────────────────────────────"
    echo "Running: $demo_path"
    echo "Log: $logfile"
    echo ""

    # Run demo with input
    echo -e "$input" | timeout 600 ./venv/bin/python "$demo_path" > "$logfile" 2>&1
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "✓ PASSED"
    elif [ $exit_code -eq 124 ]; then
        echo "✗ TIMEOUT (10 minutes)"
    else
        echo "✗ FAILED (exit code: $exit_code)"
    fi

    echo ""
    return $exit_code
}

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TIMEOUT=0

# 1. Learning Demo (quickest, no LLM needed for existing data)
run_demo "learning_demo" "examples/learning_demo.py" "no"
case $? in
    0) ((TESTS_PASSED++)) ;;
    124) ((TESTS_TIMEOUT++)) ;;
    *) ((TESTS_FAILED++)) ;;
esac

# 2. Goal Decomposition Demo (moderate)
run_demo "goal_decomposition_demo" "examples/goal_decomposition_demo.py" "no\nno"
case $? in
    0) ((TESTS_PASSED++)) ;;
    124) ((TESTS_TIMEOUT++)) ;;
    *) ((TESTS_FAILED++)) ;;
esac

# 3. Summarization Demo (skip actual simulation)
run_demo "summarization_demo" "examples/summarization_demo.py" "no"
case $? in
    0) ((TESTS_PASSED++)) ;;
    124) ((TESTS_TIMEOUT++)) ;;
    *) ((TESTS_FAILED++)) ;;
esac

# 4. Auto Goal Demo (moderate)
run_demo "auto_goal_demo" "examples/auto_goal_demo.py" "no"
case $? in
    0) ((TESTS_PASSED++)) ;;
    124) ((TESTS_TIMEOUT++)) ;;
    *) ((TESTS_FAILED++)) ;;
esac

# 5. Introspection Demo (longest, skip scenario)
run_demo "introspection_demo" "examples/introspection_demo.py" "no"
case $? in
    0) ((TESTS_PASSED++)) ;;
    124) ((TESTS_TIMEOUT++)) ;;
    *) ((TESTS_FAILED++)) ;;
esac

# Summary
echo "======================================================================"
echo "TEST SUMMARY"
echo "======================================================================"
echo "Passed:  $TESTS_PASSED"
echo "Failed:  $TESTS_FAILED"
echo "Timeout: $TESTS_TIMEOUT"
echo "======================================================================"
echo ""
echo "Check individual logs in $LOGDIR/ for details"
echo ""

if [ $TESTS_FAILED -eq 0 ] && [ $TESTS_TIMEOUT -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed or timed out"
    exit 1
fi
