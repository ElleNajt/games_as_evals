# Test Suite

## Test Organization

- `test_config_layer.py` - Fast unit tests for configuration validation (no Modal required)
- `test_expensive_integration.py` - Expensive integration tests that hit real Modal deployments

## Running Tests

### Unit Tests (Fast, No Modal Required)

```bash
python src/tests/test_config_layer.py
```

These tests use mocks and run in <1 second. Use these for TDD and quick validation.

### Expensive Integration Tests (Require Modal Deployment)

**Prerequisites:**
- Modal authenticated: `modal setup`
- 8B service deployed: `modal deploy src/modal_deployments/unified_probe_service.py::app_8b`
- (Optional) 70B service deployed: `modal deploy src/modal_deployments/unified_probe_service.py::app_70b`

**With pytest (if installed):**

```bash
# Skip expensive tests by default (normal pytest run)
pytest src/tests/

# Run ONLY expensive tests
pytest src/tests/test_expensive_integration.py -m expensive -v -s

# Run 8B tests only
pytest src/tests/test_expensive_integration.py -m expensive -k '8B' -v -s

# Run specific test
pytest src/tests/test_expensive_integration.py::TestTTLGame8B::test_ttl_8b_both_probes -v -s
```

**Without pytest:**

The test file can be run directly as a Python script to manually verify functionality:

```bash
# Just import the test to verify syntax
python -c "import src.tests.test_expensive_integration; print('✓ Test file syntax valid')"
```

To actually run the tests, use pytest as shown above.

## Test Coverage

### Backend Integration Tests (8B)
- `test_8b_single_probe_deception` - Single deception probe
- `test_8b_single_probe_hallucination` - Single hallucination probe  
- `test_8b_both_probes` - Both probes simultaneously

### TTL Game Tests (8B)
- `test_ttl_8b_hallucination_only` - 1 round with hallucination probe
- `test_ttl_8b_both_probes` - 1 round with both probes

### Backend Integration Tests (70B) - SKIPPED BY DEFAULT
- `test_70b_single_probe_deception` - Single deception probe
- `test_70b_both_probes` - Both probes simultaneously

### TTL Game Tests (70B) - SKIPPED BY DEFAULT
- `test_ttl_70b_both_probes` - 1 round with both probes

70B tests are skipped by default because they require:
- 4x H100 GPUs (expensive)
- Separate deployment of `unified-probe-service-70b`

To enable 70B tests, remove the `@pytest.mark.skip` decorator from the 70B test classes.

## Cost Considerations

**8B tests:**
- ~$0.10-0.20 per full test run
- Uses 1x A10G GPU
- Takes ~2-3 minutes

**70B tests (if enabled):**
- ~$2-5 per full test run  
- Uses 4x H100 GPUs
- Takes ~5-10 minutes

Use unit tests during development. Only run expensive integration tests when:
- Verifying end-to-end functionality after major changes
- Before deploying to production
- Debugging issues that can't be reproduced with mocks
