# Chat File Attachments — Design Spec

> **For agentic workers:** Use superpowers:writing-plans to implement this spec.

**Goal:** Allow users to paste images and upload bank-statement PDFs directly in the Chat view — files are sent to the backend, expenses are automatically extracted and saved to Sheets, and Claude responds naturally in the chat thread.

**Scope:** `chat.py`, `claude_parser.py`, `Chat.tsx`, `api.ts`, `test_chat.py`, `test_claude_parser.py`.

---

## Backend

### `chat.py` — endpoint signature

Change from a JSON body to `multipart/form-data`, matching the pattern of the existing CSV import endpoint:

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    history: str = Form("[]"),        # JSON-serialized List[ChatMessage]
    file: Optional[UploadFile] = File(None),
    sheets: SheetsClient = Depends(_get_sheets_client),
):
```

`history` is deserialized with `json.loads(history)` inside the handler.

### File handling logic

```
if file:
    content_type = file.content_type or ""
    file_bytes = await file.read()
    if content_type.startswith("image/"):
        saved, skipped_count = extract_and_save(parse_receipt_image(file_bytes, content_type), sheets)
        file_block = {"type": "image", "source": {"type": "base64",
                       "media_type": content_type, "data": base64(file_bytes)}}
    elif content_type == "application/pdf":
        saved, skipped_count = extract_and_save(parse_pdf_statement(file_bytes), sheets)
        file_block = {"type": "document", "source": {"type": "base64",
                       "media_type": "application/pdf", "data": base64(file_bytes)}}
    else:
        raise HTTPException(400, "Unsupported file type. Send an image or PDF.")
```

The Claude messages list includes a user content block with both the file block and the text:
```python
messages.append({
    "role": "user",
    "content": [file_block, {"type": "text", "text": message}]
})
```

When no file is attached the user content block is a plain string (existing behaviour).

The save-and-duplicate-check logic (`extract_and_save`) is refactored into a helper that takes a `List[ParsedExpense]` and the sheets client, returns `(saved: List[Transaction], skipped_count: int)`. This removes duplication between the text path and the file path.

### `claude_parser.py` — new function

```python
def parse_pdf_statement(pdf_bytes: bytes) -> List[ParsedExpense]:
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=2048,           # statements can be long
        system=_TEXT_SYSTEM,       # reuse existing system prompt
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64",
                            "media_type": "application/pdf",
                            "data": b64}},
                {"type": "text",
                 "text": f"Extract all expense transactions and return a JSON array matching: {schema}"},
            ],
        }],
    )
    log_usage(response, "parse_pdf_statement")
    return _parse_response(response.content[0].text)
```

Uses the same `_parse_response`, `_JSON_SCHEMA`, and confidence filter (`>= 0.5`) as the existing image and text parsers. `max_tokens` raised to 2048 because bank statements can contain many transactions.

---

## Frontend

### `Chat.tsx` — new state

```ts
const [attachedFile, setAttachedFile] = useState<File | null>(null);
const fileInputRef = useRef<HTMLInputElement>(null);
```

### Clipboard paste

`onPaste` handler on the outermost `<div>`:

```ts
const handlePaste = (e: React.ClipboardEvent) => {
  const file = e.clipboardData.files[0];
  if (file && file.type.startsWith("image/")) {
    e.preventDefault();
    setAttachedFile(file);
  }
};
```

Non-image clipboard content (text) falls through to the textarea normally.

### File button

A 📎 button inside the input bar triggers a hidden file input:

```tsx
<input
  ref={fileInputRef}
  type="file"
  accept="image/*,application/pdf"
  style={{ display: "none" }}
  onChange={e => setAttachedFile(e.target.files?.[0] ?? null)}
/>
<button onClick={() => fileInputRef.current?.click()} title="Attach image or PDF">
  📎
</button>
```

### Attachment preview

Rendered inside the input bar above the textarea when `attachedFile` is set:

- **Image**: `<img src={URL.createObjectURL(attachedFile)} />` thumbnail (max 60px tall) + × button
- **PDF**: filename chip (e.g. `statement.pdf`) + × button

Clicking × calls `setAttachedFile(null)` and resets the file input value.

### File size guard

Before setting `attachedFile`, reject files larger than 10 MB with an inline error message: `"File too large (max 10 MB)."` (10 MB = Anthropic API document limit).

### Sending

```ts
const send = async () => {
  // build FormData always (simplifies the code path)
  const form = new FormData();
  form.append("message", text);
  form.append("history", JSON.stringify(history));
  if (attachedFile) form.append("file", attachedFile);
  const { reply } = await api.chatForm(form);
  setAttachedFile(null);
  // reset file input
  if (fileInputRef.current) fileInputRef.current.value = "";
};
```

### Message bubble display

User bubble shows an attachment indicator before the text:
- Image: `<img>` thumbnail (max-width 200px)
- PDF: `📄 filename.pdf` label

The `ChatMessage` type gains an optional `attachment` field used only for display:
```ts
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  attachment?: { type: "image" | "pdf"; label: string; dataUrl?: string };
}
```

`dataUrl` is set for images (so the thumbnail persists in history), absent for PDFs (not stored — too large). `localStorage` saves the full `ChatMessage` array; for images the `dataUrl` is the base64 preview URL.

---

## API client (`api.ts`)

Replace `api.chat` with `api.chatForm`:

```ts
chatForm: (form: FormData) =>
  req<{ reply: string }>("/api/chat", { method: "POST", body: form }),
```

The `req` helper already skips `Content-Type` for `FormData` (line 8 in current `api.ts`), so no change needed there.

---

## Error handling

| Scenario | Behaviour |
|----------|-----------|
| Unsupported file type | Backend returns 400; frontend shows error in chat thread |
| File > 10 MB | Frontend rejects before upload, shows inline error |
| PDF with no parseable transactions | `parse_pdf_statement` returns `[]`; Claude responds naturally; nothing saved |
| Anthropic API failure | Existing `try/except` in chat endpoint returns 500; frontend shows "Something went wrong" |

---

## Testing

**`test_claude_parser.py`** — add two tests for `parse_pdf_statement`:
- Valid PDF bytes → mock `_client.messages.create` → returns `List[ParsedExpense]`
- Malformed JSON response → returns `[]`

**`test_chat.py`** — update existing 3 tests to send form fields instead of JSON body. Add two new tests:
- `test_chat_with_image_file` — mock `parse_receipt_image`, verify expense saved
- `test_chat_with_pdf_file` — mock `parse_pdf_statement`, verify expenses saved
