# TODO: Simplify Probe API

## Problem

Currently both `PlayerConfig` and `ModalBackend` accept both `probe` (singular) and `probes` (list) for backwards compatibility. This creates confusion and complexity:

1. **PlayerConfig** has both fields:
   - `probe: Optional[str]` - Single probe (backwards compat)
   - `probes: Optional[List[str]]` - List of probes (preferred)
   - In `__post_init__`, converts `probe` to `probes` list internally
   - Raises error if both are specified

2. **ModalBackend** has same dual API:
   - `probe: Optional[str]` - Single probe (backwards compat)
   - `probes: Optional[List[str]]` - List of probes (preferred)
   - In `__init__`, converts `probe` to `probes` list internally
   - Raises error if both are specified

3. **Duplication of logic**: Same conversion logic exists in both places

## Proposed Solution

**Remove `probe` field entirely, use only `probes` (plural list):**

```python
@dataclass
class PlayerConfig:
    name: str
    backend_type: str
    model: str
    probes: Optional[List[str]] = None  # Always a list, can be empty
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = ""
    
    # No probe field, no __post_init__ conversion needed
```

```python
class ModalBackend(LLMBackend):
    def __init__(
        self,
        probes: Optional[List[str]] = None,  # Only one parameter
        modal_app_name: Optional[str] = None,
        top_k_logits: int = 0,
        **kwargs,
    ):
        self.probe_names = probes or []
        self.top_k_logits = top_k_logits
        # No conversion logic needed
```

## Benefits

1. **Simpler API** - One way to do it
2. **Less code** - No conversion logic needed
3. **Clearer intent** - `probes` is always a list
4. **Consistent** - Backend already treats it as list internally

## Migration

For users who want a single probe:
```python
# Old way (deprecated):
PlayerConfig(probe="deception_8b")

# New way:
PlayerConfig(probes=["deception_8b"])
```

## Status

- [x] Update PlayerConfig to remove `probe` field
- [x] Update ModalBackend to remove `probe` parameter
- [x] Update all example scripts to use `probes=["name"]`
- [x] Update all game configs (WerewolfConfig, TTLConfig, CheatConfig)
- [ ] Update documentation (if needed)
- [x] ~~Add deprecation warning if needed for gradual migration~~ (Not needed - clean break)

## Notes

The backend already handles multiple probes correctly - this is purely an API simplification.
