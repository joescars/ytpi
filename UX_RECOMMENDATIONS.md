# ytpi User Experience Recommendations

This document captures the findings from a browser-based review of the ytpi download form and dashboard. Each recommendation includes a standalone implementation prompt that can be given to a coding agent later.

## Recommended delivery order

1. Preserve form input and provide visible action feedback.
2. Replace raw URLs and job IDs with meaningful media information.
3. Prevent polling from disrupting focus, selection, and scrolling.
4. Improve saved playlist cards and sync behavior.
5. Redesign the download list for desktop and mobile.
6. Improve navigation, filtering, progress reporting, accessibility, and recovery.

---

## 1. Preserve form input after validation errors

### Problem

When a submission fails validation, the entered URLs, category, quality, and other settings are discarded. Users must reconstruct the form after correcting one error.

### Recommendation

Re-render the submitted values, identify the specific invalid URL or line, display an inline error near the URL field, and move keyboard focus to the error or invalid field. Preserve custom-category and audio-only field visibility.

### Acceptance criteria

- Every submitted field retains its value after an HTML form validation error.
- The error identifies which URL or line is invalid.
- The error is associated with the URL field for assistive technology.
- Focus moves to the error summary or invalid field.
- JSON API behavior remains compatible.
- Tests cover retained video, playlist, category, quality, and audio settings.

### Implementation prompt

```text
Implement form-state preservation for ytpi validation errors using test-driven development. Work from the latest main branch in a new feature branch.

When POST /download receives an invalid HTML form submission, preserve all submitted values: URLs, category, custom category, quality, audio-only state, and audio format. Identify the invalid URL or line in a user-friendly inline error, associate the error with the URL field, and move focus to the error or invalid field when the page loads. Preserve the existing JSON API response contract and CIDR access-control boundary.

Add focused Flask and frontend tests for the behavior, run the full test suite, rebuild Docker, and verify the flow in a real browser at desktop and mobile widths. Do not commit or push unless asked.
```

---

## 2. Show meaningful titles instead of raw URLs and job IDs

### Problem

Download history is dominated by truncated UUIDs and long YouTube URLs. These values are useful for diagnostics but are not the information users naturally recognize.

### Recommendation

Store and display video or playlist titles. Lead each row or card with the title, then show category, requested quality, status, and destination. Keep the URL and complete job ID in a details view or tooltip.

### Acceptance criteria

- Jobs persist a human-readable media title when yt-dlp reports it.
- Playlist jobs reuse the saved playlist title.
- Existing jobs without titles display a concise fallback rather than a full raw URL.
- The original URL remains available as a link.
- The complete job ID remains accessible for troubleshooting.
- Titles are safely rendered as text, not HTML.

### Implementation prompt

```text
Improve ytpi download-history labels using test-driven development. Work from the latest main branch in a new feature branch.

Persist human-readable video and playlist titles from yt-dlp output and display the title as the primary label in download history. Show category, requested resolution or audio format, and status as supporting metadata. Keep the original URL as an external link and expose the complete job ID in a details area, but do not lead with raw URLs or UUIDs. Provide a concise fallback for historical jobs that do not have a title. Preserve existing jobs through a safe SQLite schema migration.

Add repository, manager, API, and UI tests. Run the full suite, rebuild Docker, and verify titles and fallbacks in a browser. Do not commit or push unless asked.
```

---

## 3. Preserve keyboard focus and scroll position during polling

### Problem

The dashboard replaces all table rows during each refresh. Keyboard focus is lost, and selection or scroll position can move unexpectedly. Automatic polling therefore makes the interface difficult to operate reliably.

### Recommendation

Update existing DOM elements by stable job ID rather than rebuilding the table. Preserve focused controls, selected jobs, horizontal table position, and output scroll behavior.

### Acceptance criteria

- A focused job or action button remains focused after polling.
- The selected job remains selected.
- Table scroll position is retained.
- Removed jobs are handled without leaving focus in an invalid state.
- New jobs appear without rebuilding unrelated rows.
- Polling remains non-overlapping.

### Implementation prompt

```text
Refactor the ytpi dashboard polling renderer using test-driven development. Work from the latest main branch in a new feature branch.

Replace full tbody reconstruction with keyed updates based on job ID. Preserve keyboard focus, selected-job state, table scroll position, and relevant output scroll behavior across automatic and manual refreshes. Correctly add, update, reorder, and remove jobs. If the focused job disappears, move focus to a sensible nearby control and announce the change. Keep polling requests non-overlapping.

Add browser-oriented JavaScript tests for focus, selection, scrolling, additions, updates, and removals. Run all tests, rebuild Docker, and verify keyboard-only operation in a real browser. Do not commit or push unless asked.
```

---

## 4. Provide visible success and error feedback for actions

### Problem

Sync, Cancel, Retry, and polling failures may be silently ignored. A failed action can look identical to a successful click, leaving users unsure whether anything happened.

### Recommendation

Use a persistent status region or toast system for actionable messages. Include server-provided error text, show pending states, restore controls after failures, and link successful actions to the affected job.

### Acceptance criteria

- Sync reports queued, syncing, success, or failure.
- Cancel and Retry report their outcomes.
- Queue-full and connection errors are visible.
- Buttons show a pending state and prevent duplicate submissions.
- Successful playlist sync focuses or links to the newly created job.
- Messages are announced through an appropriate ARIA live region.

### Implementation prompt

```text
Add reliable action feedback to the ytpi dashboard using test-driven development. Work from the latest main branch in a new feature branch.

Create an accessible notification/status system for playlist Sync, job Cancel, job Retry, Clear completed history, and polling failures. Display useful server-provided error messages, including queue-full responses. Show pending button labels and prevent duplicate requests while an action is running. On successful playlist sync, identify and select the newly queued job. Use an ARIA live region without repeatedly announcing routine polling updates.

Add frontend and Flask integration tests for success, HTTP errors, network failures, duplicate clicks, and recovery. Run the full suite, rebuild Docker, and verify the messages in a browser. Do not commit or push unless asked.
```

---

## 5. Redesign the download list for desktop and mobile

### Problem

The table is wider than its desktop panel and requires substantial horizontal scrolling on mobile. Important information and controls are difficult to scan.

### Recommendation

Give the download list the full available width on desktop. Use responsive cards or a deliberately reduced column set on mobile. Keep title, status, progress, and actions visible without horizontal scrolling.

### Acceptance criteria

- Desktop download history uses the full content width.
- Mobile users can see title, status, progress, and primary action without horizontal scrolling.
- Secondary metadata remains available through an expandable details area.
- Touch targets are at least approximately 44px high.
- Long titles and errors wrap without breaking the layout.
- The technical-output panel remains usable below or beside the list.

### Implementation prompt

```text
Redesign the ytpi download-history layout for responsive usability using test-driven development. Work from the latest main branch in a new feature branch.

Make the history list full-width on desktop and replace the wide table with accessible stacked cards on narrow screens, or use an equivalent responsive pattern that avoids horizontal scrolling. Keep media title, status, progress, and the primary action immediately visible. Put category, requested quality, timestamps, URL, job ID, error details, and technical output in a clearly discoverable details area. Maintain semantic and keyboard-accessible controls with touch-friendly sizing.

Add responsive frontend tests, run the full test suite, rebuild Docker, and inspect the real UI at common desktop and mobile widths. Do not commit or push unless asked.
```

---

## 6. Turn saved playlists into informative, editable cards

### Problem

The database stores category, quality, audio settings, and sync time, but the dashboard only shows a playlist name and Sync button. Users cannot inspect or adjust the retained settings.

### Recommendation

Display saved settings and let users edit them. Show whether the playlist is configured for video or audio, its category, resolution or audio format, last successful sync, and current sync state.

### Acceptance criteria

- Each card shows playlist name, media mode, category, quality/audio format, and last successful sync.
- Users can edit settings with existing validation helpers.
- Editing settings does not automatically enqueue a download.
- Sync uses the newly saved settings.
- Playlist links remain available without exposing raw URLs as primary content.
- Concurrent or duplicate sync requests are clearly handled.

### Implementation prompt

```text
Upgrade saved playlists into informative, editable cards using test-driven development. Work from the latest main branch in a new feature branch.

Display each playlist's name, video or audio mode, category, requested resolution or audio format, last successful sync time, and active sync state. Add an Edit settings flow that uses the existing category, quality, audio-format, URL, and path-safety validation helpers. Saving settings must not enqueue a download; the Sync action must use the updated values. Keep the playlist name linked to YouTube while hiding the raw URL from the primary presentation.

Add repository, route, validation, and UI tests. Run the full suite, rebuild Docker, and verify editing and syncing in a browser. Do not commit or push unless asked.
```

---

## 7. Track requested, active, and successful playlist sync states correctly

### Problem

The current last-sync timestamp is updated when a sync job is queued, not when it successfully completes. It therefore does not represent the last successful synchronization.

### Recommendation

Track separate timestamps and state for requested, started, completed, and failed syncs. Link playlist sync records to their jobs and update the successful timestamp only after completion.

### Acceptance criteria

- Queuing a sync does not update `last_successful_sync_at`.
- The playlist records its active sync job.
- Successful completion updates the successful timestamp.
- Failed or cancelled syncs retain the prior successful timestamp.
- The UI shows queued, syncing, failed, and last-successful states accurately.
- App restart and queued-job recovery preserve the relationship.

### Implementation prompt

```text
Correct playlist sync lifecycle tracking in ytpi using test-driven development. Work from the latest main branch in a new feature branch.

Replace the ambiguous last_synced_at behavior with explicit requested, active, successful, and failed sync state. Associate each playlist sync with its download job. Update the last-successful timestamp only when that job finishes successfully; failures and cancellations must preserve the previous successful timestamp. Ensure queued-job recovery after restart retains the playlist relationship. Expose the state through the API and display it clearly in the playlist card.

Use a backward-compatible SQLite migration. Add end-to-end tests covering queueing, success, failure, cancellation, retry, and restart recovery. Run the full suite and rebuild Docker. Do not commit or push unless asked.
```

---

## 8. Report what changed during a playlist sync

### Problem

A completed sync only shows that yt-dlp finished. Users cannot tell whether new videos were downloaded, existing files were skipped, or some items failed.

### Recommendation

Capture structured playlist-sync results from yt-dlp output or a more stable metadata mechanism. Show counts for discovered, downloaded, already present, and failed items.

### Acceptance criteria

- The completed sync reports newly downloaded items.
- Already downloaded or skipped items are counted separately.
- Failed playlist entries are reported without requiring raw-log inspection.
- Counts persist with the sync job.
- Parsing is covered with representative real yt-dlp output fixtures.
- Raw output remains available under technical details.

### Implementation prompt

```text
Add user-friendly playlist sync result summaries to ytpi using test-driven development. Work from the latest main branch in a new feature branch.

Capture and persist structured counts for playlist items discovered, newly downloaded, already present or skipped, and failed. Prefer stable yt-dlp output options or machine-readable metadata over fragile human-log parsing where feasible. Show a concise completion summary on the playlist card and related job details while retaining raw output under Technical details. Handle partial failures honestly.

Add parser or integration fixtures based on representative yt-dlp output and end-to-end repository/API/UI tests. Run the full suite, rebuild Docker, and verify a real playlist sync if a safe test playlist is available. Do not commit or push unless asked.
```

---

## 9. Refresh playlist metadata automatically and preserve known names

### Problem

Routine dashboard polling only refreshes jobs. Playlist names or sync timestamps can remain stale until a page reload. Additionally, an upsert can replace a resolved playlist title with its playlist ID fallback.

### Recommendation

Refresh playlist data when relevant state changes and at a conservative polling interval. Never overwrite a known human-readable title with an ID fallback.

### Acceptance criteria

- A newly discovered title appears without a full page reload.
- Sync-state changes appear automatically.
- Known titles are not replaced by playlist IDs.
- A newer real title can replace an older real title.
- Playlist polling pauses while the document is hidden and avoids overlapping requests.

### Implementation prompt

```text
Make ytpi playlist metadata refresh safely and preserve readable names using test-driven development. Work from the latest main branch in a new feature branch.

Update saved-playlist data automatically after sync actions and during conservative background polling. Pause hidden-tab requests and prevent overlapping fetches. Change repository upsert behavior so a playlist-ID fallback never overwrites a known human-readable title, while a newly fetched real title may update an older title. Keep UI focus and open details stable while cards update.

Add repository and JavaScript tests for title precedence, polling, hidden-tab behavior, overlap prevention, and live updates. Run all tests and rebuild Docker. Do not commit or push unless asked.
```

---

## 10. Clarify navigation and page structure

### Problem

The home page contains two Dashboard links, while the dashboard relies on the brand link to return to the form. Downloads, playlists, and technical output compete within one page.

### Recommendation

Use consistent primary navigation with three destinations: New Download, Downloads, and Playlists. Keep the route structure simple and preserve deep links to individual jobs.

### Acceptance criteria

- Every page presents the same primary navigation.
- The current destination is visually and programmatically identified.
- Duplicate navigation links are removed.
- Deep links to jobs still work.
- Mobile navigation remains simple and keyboard accessible.
- Each page has one descriptive `h1`.

### Implementation prompt

```text
Improve ytpi information architecture and navigation using test-driven development. Work from the latest main branch in a new feature branch.

Create consistent primary navigation for New Download, Downloads, and Playlists. Remove duplicate Dashboard links, mark the current destination accessibly, and ensure every page has one descriptive h1. Separate saved-playlist browsing from download history while preserving direct job links and existing API routes. Keep the navigation compact and touch-friendly on mobile.

Add Flask template and browser tests for every route, active-state semantics, keyboard navigation, and mobile layout. Run the full suite and rebuild Docker. Do not commit or push unless asked.
```

---

## 11. Add search, filters, dates, and real pagination

### Problem

The dashboard requests at most 200 jobs and calculates visible KPI values from that subset. As history grows, users cannot reliably find old downloads, and the displayed totals may be misleading.

### Recommendation

Provide server-backed search, status/category filters, date display, and pagination. Return aggregate counts separately from the current page of results.

### Acceptance criteria

- Users can search by title, URL, filename, or job ID.
- Status and category filters can be combined.
- Jobs display useful created/finished dates.
- Pagination preserves filters and selected job state.
- KPI values represent the complete filtered dataset, not only the current page.
- Queries are indexed or bounded appropriately.

### Implementation prompt

```text
Add scalable download-history discovery to ytpi using test-driven development. Work from the latest main branch in a new feature branch.

Implement server-backed search over title, URL, filename, and job ID; combinable status and category filters; useful created and completed timestamps; and pagination. Return aggregate KPI counts independently from the current page so totals remain accurate beyond 200 records. Preserve filters in the URL and maintain the selected job when possible. Add appropriate SQLite indexes without introducing unsafe dynamic SQL.

Add repository query tests, API tests, and browser tests for search, filter combinations, pagination, empty states, and accurate totals. Run the full suite and rebuild Docker. Do not commit or push unless asked.
```

---

## 12. Replace raw logs with a concise job details view

### Problem

The command output occupies a large, prominent area even though most users primarily need the result, destination, progress, and any corrective action.

### Recommendation

Create a user-focused job details panel. Show media title, destination, requested settings, current stage, final result, and clear error guidance. Put raw yt-dlp logs inside a collapsed Technical details section.

### Acceptance criteria

- Job details lead with understandable state and media information.
- The requested settings and destination are visible.
- Errors include a concise summary and relevant Retry action.
- Raw output is collapsed by default but remains copyable.
- The selected-job details update without losing user scroll or focus.

### Implementation prompt

```text
Redesign ytpi job details around user outcomes using test-driven development. Work from the latest main branch in a new feature branch.

Replace the raw-log-first panel with a concise details view containing media title, status, requested category and quality or audio format, destination, timestamps, current processing stage, and an actionable error summary. Put raw yt-dlp output inside a collapsed Technical details disclosure with a Copy output action. Preserve selection, focus, and intentional log scroll position during polling.

Add API fields only where needed, with repository and frontend tests. Run the full suite, rebuild Docker, and verify active, finished, failed, and cancelled jobs in a browser. Do not commit or push unless asked.
```

---

## 13. Make progress accurately represent playlists and processing stages

### Problem

A playlist job can show 100% for an individual file before the playlist is complete. Conversion and metadata steps are also not clearly distinguished from downloading.

### Recommendation

Track playlist item position separately from current-item transfer progress. Expose a user-friendly stage such as Preparing, Downloading item 3 of 7, Converting, Finalizing, or Finished.

### Acceptance criteria

- Playlist-level and current-item progress are distinct.
- A playlist is not represented as complete until the full job succeeds.
- Post-processing stages are visible.
- Progress remains meaningful when totals are initially unknown.
- Retry resets stale progress fields correctly.
- Progress bars have accessible names.

### Implementation prompt

```text
Improve ytpi download progress semantics using test-driven development. Work from the latest main branch in a new feature branch.

Track and expose a user-facing processing stage plus separate playlist item position and current-file transfer percentage. Display states such as Preparing, Downloading item 3 of 7, Converting audio, Adding metadata, Finalizing, and Finished. Never show the whole playlist as 100% merely because one file completed. Support initially unknown playlist totals and ensure retry clears stale progress. Give every progress bar an accessible name tied to its job title.

Add representative yt-dlp output fixtures and manager, repository, API, and frontend tests. Run the full suite and rebuild Docker. Do not commit or push unless asked.
```

---

## 14. Improve history-cleanup wording and safety

### Problem

The Clear Finished control also removes error and cancelled jobs, while its wording does not explain whether downloaded files will be deleted.

### Recommendation

Rename it to Clear completed history and use a confirmation dialog that explicitly lists affected statuses and states that downloaded files will remain. Consider allowing status-specific cleanup.

### Acceptance criteria

- The label accurately describes history removal.
- Confirmation explains that files are not deleted.
- The affected statuses are clear.
- The completion message reports counts by status where feasible.
- Users can cancel without changing data.

### Implementation prompt

```text
Clarify and harden ytpi history cleanup using test-driven development. Work from the latest main branch in a new feature branch.

Rename Clear Finished to Clear completed history. Replace the generic browser confirmation with an accessible application dialog explaining that finished, failed, and cancelled history records will be removed while downloaded files remain untouched. Report the number of records removed, preferably by status, and keep the operation cancellable. Consider status-specific choices only if they can be added without unnecessary complexity.

Add route, repository, and browser tests. Run the full suite, rebuild Docker, and verify keyboard and mobile dialog behavior. Do not commit or push unless asked.
```

---

## 15. Improve connection-loss and stale-data recovery

### Problem

Polling errors are suppressed, which can leave stale information on screen with no indication that the dashboard is disconnected.

### Recommendation

Display connection state and last-updated time. Use retry backoff, announce transitions rather than every failed poll, and make manual Refresh retry both jobs and playlists.

### Acceptance criteria

- The dashboard shows last successful update time.
- Connection loss produces a visible but non-disruptive warning.
- Recovery clears the warning and announces reconnection once.
- Polling uses bounded backoff during repeated failures.
- Manual Refresh updates jobs and playlists.
- Existing data remains visible while marked as potentially stale.

### Implementation prompt

```text
Add resilient connection-state UX to the ytpi dashboard using test-driven development. Work from the latest main branch in a new feature branch.

Show the last successful refresh time and a visible stale-data warning when jobs or playlist polling fails. Keep existing data visible, use bounded retry backoff, and announce only connection-loss and recovery transitions through an ARIA live region. Make the manual Refresh action retry both jobs and playlists and show its outcome. Pause routine polling when the page is hidden.

Add deterministic JavaScript tests with mocked time and fetch responses, then run the full suite, rebuild Docker, and verify offline/recovery behavior in a browser. Do not commit or push unless asked.
```

---

## 16. Explain context-sensitive form behavior

### Problem

Selecting audio-only hides category and disables quality without explaining that downloads will be stored under the `audio-only` category. Users may perceive the disappearing fields as data loss.

### Recommendation

Show concise contextual guidance when audio-only is selected. Make it clear which settings are ignored and where files will be stored. Also preview whether an entered YouTube URL will be treated as a video or playlist.

### Acceptance criteria

- Audio-only mode explains its destination category and selected format.
- Hidden or disabled settings are explained.
- Switching modes restores the user's previous selections where safe.
- YouTube playlist URLs are identified before submission.
- A watch URL containing playlist context has an explicit download-scope choice if behavior would otherwise be ambiguous.

### Implementation prompt

```text
Improve context-sensitive guidance on the ytpi download form using test-driven development. Work from the latest main branch in a new feature branch.

When audio-only mode is enabled, explain that video quality is not used and that output is stored under the audio-only category, including the selected audio format. Preserve the user's previous category and quality selections when switching back. Detect whether entered YouTube URLs represent videos or playlists and show a non-blocking preview before submission. For watch URLs that also contain playlist context, make the intended download scope explicit rather than surprising the user.

Keep server-side validation authoritative. Add frontend and route tests, run the full suite, rebuild Docker, and verify the form with keyboard and mobile interactions. Do not commit or push unless asked.
```

---

## 17. Complete an accessibility pass

### Problem

Progress bars lack accessible names, the dashboard lacks a clear primary heading, and live regions may announce overly broad content changes. Motion preferences are not respected.

### Recommendation

Improve headings, labels, focus visibility, live-region scope, progress semantics, keyboard operation, contrast, and reduced-motion behavior.

### Acceptance criteria

- Every page has a descriptive `h1` and logical heading order.
- Every progress bar has an accessible name and value.
- Status updates are concise and not repeatedly announced.
- All controls work by keyboard with visible focus.
- Dialogs trap and restore focus appropriately.
- `prefers-reduced-motion` disables nonessential animation.
- Automated accessibility checks and manual keyboard checks pass.

### Implementation prompt

```text
Perform a focused accessibility improvement pass on ytpi using test-driven development. Work from the latest main branch in a new feature branch.

Fix page heading structure, progress-bar accessible names, form error associations, visible focus states, keyboard operation, status live regions, dialog focus handling, touch target sizing, and reduced-motion support. Verify color contrast and avoid announcing the entire polling table on routine updates. Preserve the existing visual identity and functionality.

Add automated accessibility checks where practical plus semantic and keyboard interaction tests. Run the full test suite, rebuild Docker, and manually verify keyboard-only use at desktop and mobile widths. Document any remaining screen-reader testing limitations. Do not commit or push unless asked.
```

---

## General implementation constraints

Every implementation should preserve these project invariants:

- Keep the CIDR allowlist `before_request` security boundary intact.
- Continue using the existing URL, category, quality, and audio-format validation helpers.
- Keep category paths under `YTPI_DOWNLOADS_DIR`.
- Preserve persisted queued jobs and restart recovery.
- Keep `YTPI_MAX_WORKERS=0` behavior available for tests.
- Use test-driven development and run the full test suite.
- Rebuild Docker and verify the real application after frontend or runtime changes.
- Do not include the local untracked `CLAUDE.md` unless explicitly requested.
