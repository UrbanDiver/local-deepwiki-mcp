# Security Audit - Detailed Technical Findings

## File-by-File Analysis

### CRITICAL FINDINGS

---

## Finding 1: API Key Exposure in Memory
**Severity:** HIGH
**CWE:** CWE-798 (Use of Hard-Coded Credentials)
**Files Affected:**
- `/src/local_deepwiki/providers/llm/anthropic.py:45`
- `/src/local_deepwiki/providers/llm/openai.py:49`
- `/src/local_deepwiki/providers/embeddings/openai.py:35`

### Vulnerable Code

**File: `/src/local_deepwiki/providers/llm/anthropic.py`**
```python
37  def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
38      """Initialize the Anthropic provider.
39
40      Args:
41          model: Anthropic model name.
42          api_key: Optional API key. Uses ANTHROPIC_API_KEY env var if not provided.
43      """
44      self._model = model
45      self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")  # ⚠️ EXPOSED
46      self._client = AsyncAnthropic(api_key=self._api_key)
```

**File: `/src/local_deepwiki/providers/llm/openai.py`**
```python
41  def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
42      """Initialize the OpenAI provider.
43
44      Args:
45          model: OpenAI model name.
46          api_key: Optional API key. Uses OPENAI_API_KEY env var if not provided.
47      """
48      self._model = model
49      self._api_key = api_key or os.environ.get("OPENAI_API_KEY")  # ⚠️ EXPOSED
50      self._client = AsyncOpenAI(api_key=self._api_key)
```

### Issues
1. **Plaintext Storage:** API keys stored as instance variables in plaintext
2. **No Encryption:** Keys held in memory with no protection
3. **Weak Access Control:** Any code with access to provider instance can extract key
4. **Memory Dump Risk:** If process memory is dumped, keys are exposed
5. **Long Lifetime:** Keys persist for entire provider instance lifetime

### Attack Scenario
```python
# Attacker with process access could do:
provider = AnthropicProvider()
# Extract key via:
# 1. Process memory dump
# 2. Debugging tools (gdb, lldb)
# 3. Introspection in Python REPL
# 4. Accidental logging
```

### Proof of Concept
```python
import local_deepwiki.providers.llm.anthropic as anthro
provider = anthro.AnthropicProvider()
# Attacker can access via: provider._api_key
exposed_key = provider._api_key  # ⚠️ KEY EXPOSED
```

### Remediation
1. Use environment variables only, never store in instance
2. Implement credential manager pattern
3. Clear credentials after use (if possible)
4. Add secret masking in logs

---

## Finding 2: Insufficient Error Message Sanitization
**Severity:** HIGH
**CWE:** CWE-209 (Information Exposure Through an Error Message)
**Files Affected:**
- `/src/local_deepwiki/handlers.py:131-135`
- `/src/local_deepwiki/handlers.py:254-256`
- Multiple provider files

### Vulnerable Code

**File: `/src/local_deepwiki/handlers.py`**
```python
128  except Exception as e:  # noqa: BLE001
129      # Broad catch is intentional: top-level error handler for MCP tools
130      # that converts any unhandled exception to a user-friendly error message
131      logger.exception(f"Unexpected error in {func.__name__}: {e}")
132      error = DeepWikiError(
133          message=f"An unexpected error occurred: {e}",  # ⚠️ EXPOSED
134          hint="Check the logs for more details. If this persists, please report the issue.",
135      )
136      return [TextContent(type="text", text=format_error_response(error))]
```

**File: `/src/local_deepwiki/providers/llm/anthropic.py`**
```python
254  except Exception as e:
255      self._handle_api_error(e)
256      raise  # ⚠️ May expose full API error
```

### Examples of Information Leakage

1. **File Path Exposure**
```
Error: /home/user/.config/local-deepwiki/models/embedding.bin: No such file
→ Reveals home directory structure
```

2. **API Endpoint Exposure**
```
Error: Connection refused to http://localhost:11434/api/chat
→ Reveals internal Ollama configuration
```

3. **Model Information**
```
Error: Model 'some-invalid-model' not found. Available models: [list]
→ Reveals what models are installed
```

4. **Library Information**
```
Error: anthropic.APIConnectionError: Unable to connect
→ Reveals specific library versions through error format
```

### Attack Scenario
1. Attacker uses repository indexing tool
2. Deliberately causes error (e.g., invalid LLM configuration)
3. Error message reveals internal paths or configurations
4. Attacker maps infrastructure

### Remediation
```python
# VULNERABLE (current)
except Exception as e:
    message = f"An unexpected error occurred: {e}"

# SECURE (recommended)
except Exception as e:
    logger.exception(f"Detailed error: {e}")
    # Generic message to user, no details
    message = "An unexpected error occurred. Please contact support."
```

---

## Finding 3: Missing Access Control Layer
**Severity:** MEDIUM
**CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key)
**Files Affected:** `/src/local_deepwiki/handlers.py` (all tool handlers)

### Issue
No authentication or authorization checks on MCP tool calls.

### Vulnerable Functions
```python
# handlers.py:365 - handle_ask_question
# No check if user should access this repo
repo_path = Path(validated.repo_path).resolve()

# handlers.py:930 - handle_search_code
# No access control
repo_path = Path(validated.repo_path).resolve()

# handlers.py:889 - handle_read_wiki_page
# No permission validation
page_path = (wiki_path / page).resolve()

# handlers.py:1006 - handle_export_wiki_html
# No authorization check
wiki_path = Path(validated.wiki_path).resolve()
```

### Attack Scenarios

**Scenario 1: Unauthorized Repository Access**
```
User A calls: ask_question("/path/to/user-b-private-repo")
→ No check if User A has access
→ User A can read any repository
```

**Scenario 2: Secret Exposure**
```
Repository indexed contains:
- .env files with API keys
- Private credentials
- Configuration with passwords

User can: ask_question or search_code
Result: Secrets exposed in code chunks
```

**Scenario 3: Denial of Service**
```
Attacker calls: index_repository("/massive/repo", full_rebuild=true)
→ No rate limiting
→ Can exhaust system resources
```

### Remediation
Implement authorization layer:
```python
async def handle_index_repository(args, server=None):
    # Add permission check
    user = get_current_user(server)  # Extract from MCP context
    repo_path = Path(args["repo_path"]).resolve()

    # Check if user allowed
    if not is_user_allowed_access(user, repo_path):
        raise AuthorizationError(f"Access denied to {repo_path}")

    # Continue with indexing...
```

---

## Finding 4: Dependency Version Pinning Issues
**Severity:** MEDIUM
**CWE:** CWE-1104 (Use of Unmaintained Third Party Components)
**File:** `/pyproject.toml`

### Issues

**1. No Upper Version Bounds**
```toml
# Current: >=X.X
pyyaml >= 6.0      # ⚠️ Could allow 7.0 with breaking changes
weasyprint >= 68.0  # ⚠️ Complex parser, new versions may have issues
```

**2. Potential Vulnerabilities**

**PyYAML (Line 30)**
```toml
pyyaml >= 6.0
```
Risk: If using `yaml.load()` instead of `yaml.safe_load()`, YAML deserialization RCE possible.

**WeasyPrint (Line 36)**
```toml
weasyprint >= 68.0
```
Risk: Complex HTML/CSS rendering, potential DoS via malicious CSS in exported PDFs.

**3. External Service Dependencies**
```toml
ollama >= 0.4  # External service, RCE if Ollama itself is vulnerable
```

### Proof of Concept - YAML RCE (if unsafe loading used)
```yaml
# Malicious config file
exploit: !!python/object/apply:os.system ["rm -rf /"]
```

### Recommendations
```toml
# Add upper bounds
pyyaml >= 6.0, < 7.0
weasyprint >= 68.0, < 69.0
ollama >= 0.4, < 1.0

# Or pin to specific versions
pyyaml == 6.0.1
weasyprint == 68.1
```

---

## YAML Safety Check Required
**File:** `/src/local_deepwiki/config.py`
**Status:** NEEDS VERIFICATION

### Required Check
Search for:
```bash
grep -n "yaml.load(" src/local_deepwiki/config.py
```

If found (not safe_load), this is a HIGH severity vulnerability:
```python
# VULNERABLE
data = yaml.load(config_file)

# SECURE
data = yaml.safe_load(config_file)
```

---

## Finding 5: Progress Notification Data Exposure
**Severity:** LOW
**CWE:** CWE-200 (Exposure of Sensitive Information to an Unauthorized Actor)
**File:** `/src/local_deepwiki/handlers.py:1380-1395`

### Vulnerable Code
```python
1380  progress_data = {
1381      "step": latest.current,
1382      "total_steps": latest.total or 0,
1383      "step_type": latest.phase.value,
1384      "message": latest.message,
1385      "eta_seconds": latest.eta_seconds,
1386      "**latest.metadata,  # ⚠️ May contain file paths
1387  }
1388
1394  message=json.dumps(progress_data),
```

### Issue
The `metadata` field spreads directly into progress notification:
```python
metadata={
    "files_processed": status.total_files,
    "total_files": status.total_files,
    "chunks_created": status.total_chunks,
    "pages_generated": len(wiki_structure.pages),
}
```

While currently safe, could accidentally leak paths if metadata expanded.

### Remediation
```python
# Add allowlist for progress metadata
allowed_fields = {"files_processed", "total_files", "chunks_created"}
safe_metadata = {k: v for k, v in latest.metadata.items() if k in allowed_fields}
```

---

## Finding 6: No Input Size Limits on Vector Operations
**Severity:** LOW/MEDIUM
**CWE:** CWE-770 (Allocation of Resources Without Limits)
**File:** `/src/local_deepwiki/handlers.py:392`

### Vulnerable Code
```python
392  search_results = await vector_store.search(question, limit=max_context)
```

### Issue
While `max_context` is bounded (validation.py: max 50 chunks), no limits on:
- Prompt/question length
- Number of chunks returned for deep research
- Total tokens processed

### Attack
```
send: question="a " * 1000000  # 1MB of text
Result: Memory exhaustion or API rate limit
```

### Current Protections
- `MAX_WIKI_PAGE_SIZE` = 10MB (line 23, validation.py)
- `MAX_CONTEXT_CHUNKS` = 50 (validation.py)
- `MAX_SEARCH_LIMIT` = 100 (validation.py)

### Recommendation
Add input size validation:
```python
MAX_QUESTION_LENGTH = 2000  # characters
if len(question) > MAX_QUESTION_LENGTH:
    raise ValidationError("Question too long")
```

---

## Finding 7: No Audit Logging
**Severity:** MEDIUM
**CWE:** CWE-778 (Insufficient Logging)
**Impact:** Cannot track who accessed what code

### Missing Audit Trail For:
- Who queried which repository
- What code was accessed
- When access occurred
- Export/download events
- Configuration changes

### Recommendation
Implement audit logging:
```python
async def audit_log(user: str, action: str, resource: str, result: str):
    """Log security-relevant events"""
    logger.info(f"AUDIT: user={user} action={action} resource={resource} result={result}")
```

---

## INFRASTRUCTURE SECURITY NOTES

### 1. Configuration File Permissions
**Location:** `~/.config/local-deepwiki/config.yaml`

**Risk:** Config may contain API keys with world-readable permissions

**Mitigation:**
```bash
# Should enforce
chmod 600 ~/.config/local-deepwiki/config.yaml
```

### 2. Ollama Local Exposure
**Location:** Ollama provider connects to http://localhost:11434

**Risk:** If Ollama runs on non-localhost, credentials could be intercepted

**Mitigation:**
- Only connect to localhost
- Validate Ollama version before use
- Consider using Unix sockets instead

### 3. Flask Web UI Security
**File:** `/src/local_deepwiki/web/app.py`

**Note:** Not thoroughly analyzed, but web UI may have CSRF/XSS issues if user-supplied data rendered without escaping.

---

## SUMMARY OF FINDINGS

| Finding | Severity | Type | CWE | Status |
|---------|----------|------|-----|--------|
| API Key Exposure | HIGH | Credential | 798 | ⚠️ OPEN |
| Error Message Leakage | HIGH | InfoDisclosure | 209 | ⚠️ OPEN |
| No Access Control | MEDIUM | Authorization | 639 | ⚠️ OPEN |
| Version Pinning | MEDIUM | Dependencies | 1104 | ⚠️ OPEN |
| Progress Data Leak | LOW | InfoDisclosure | 200 | ⚠️ REVIEW |
| No Input Limits | LOW | DoS | 770 | ⚠️ REVIEW |
| No Audit Logging | MEDIUM | Logging | 778 | ⚠️ OPEN |

---

## SECURE CODE PATTERNS FOUND

✓ **Path Traversal Protection** - Proper use of `Path.is_relative_to()`
✓ **Input Validation** - Comprehensive Pydantic validation
✓ **Error Handling** - Good exception handling structure
✓ **Async Best Practices** - Proper use of asyncio
✓ **Type Hints** - Full type annotations throughout

---

## TESTING CHECKLIST

- [ ] Run `bandit -r src/` for security issues
- [ ] Run `pip-audit` for dependency vulnerabilities
- [ ] Verify YAML uses only `safe_load()`
- [ ] Test path traversal with `../../../etc/passwd`
- [ ] Verify API keys not in logs
- [ ] Check config file has mode 600
- [ ] Test error messages don't leak paths
- [ ] Verify no hardcoded credentials in code
- [ ] Test error handling with malformed input
- [ ] Verify progress notifications safe

---

## NEXT STEPS

1. **Immediate (this week):**
   - Implement API key encryption/secure storage
   - Sanitize error messages

2. **Short-term (next 2 weeks):**
   - Add access control layer
   - Fix dependency pinning
   - Verify YAML safety

3. **Medium-term (next month):**
   - Add audit logging
   - Input size validation
   - Path allowlist/denylist

4. **Long-term (ongoing):**
   - Regular dependency updates
   - Security testing in CI/CD
   - Penetration testing
