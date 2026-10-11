# AI interview frontend

`dashboard.html` is the workspace shell. It owns the sidebar, topbar, authenticated user, language selection, navigation badges and URL hash. One same-origin iframe displays an independent HTML page and owns content scrolling.

## Pages

- `home.html`: existing dashboard statistics and sample/local invitation lists.
- `interview-create.html`: existing invitation preview form and success view.
- `interviews.html`: interview list with candidate search, status and creation-date filters.
- `reports.html`: simulated report list, plain-text detail and independent audio/video playback.
- `help.html`, `settings.html`, `plan.html`, `account.html`: independent entry pages for features that are not implemented yet.

Routes use `dashboard.html#home`, `#create`, `#interviews`, etc. The shell replaces the iframe document's history entry so browser Back follows the shell routes. Open pages through an HTTP server on the same origin, not `file://`.

## Shared integration

Each function page loads `js/common.js` for API access and `js/frame.js` for shell communication. Page scripts listen for `aomera-language-change` and `aomera-user-ready`; the bridge sends its ready message after their listeners are installed. Language updates continue throughout the page lifetime. User readiness is emitted once per user ID.

`window.AIInterviewFrame` provides:

- `user` and `lang`: the current shell context.
- `navigate(route)`: navigate the outer workspace, or open the workspace when a function page is accessed directly.
- `records(userId)`: read validated local invitation previews.
- `recordsUpdated()`: notify the shell to refresh navigation counts.

Messages are checked against the same origin and the expected parent/iframe window. Function pages opened directly request `/me` themselves.

Creation drafts use per-user `sessionStorage` and survive menu changes and reloads in the current tab. Successful creation clears the draft; creating another interview resets the form. Invitation previews still use per-user `localStorage`; links remain demonstration URLs and do not issue live invitations.

## Report interaction demo

`js/reports-demo.js` provides four simulated reports (three initially unread),
including two interviews for the same candidate. Reports are plain text.
Reading state is saved in per-user localStorage and updates the sidebar badge.
The report page does not call any report API or access the database.
The existing workspace authentication remains unchanged.

Local sample audio/video files only demonstrate playback controls; they are
not candidate recordings. The detail preserves the list filter and scroll
position when returning to the list.
