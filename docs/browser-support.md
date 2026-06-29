# Browser Support Documentation

Tests on:

- Chrome
- Firefox
- Safari (?)
- Edge
- Mobile

Use:

```bash
make upd-build
```

Then open:

```text
https://localhost:8443
```

## Tests

| Area | What to verify |
| --- | --- |
| App shell | Home/graph page loads, navigation, theme styling, layout overlap (mobile may have this)|
| Authentication | Register, log in, log out. |
| Graph | Graph canvas: zoom/drag/click interactions work, filters update the visible graph, and the details panel. |
| Search | Search input, keyboard interaction, filters, selected result|
| Dashboard | loads metrics, user-management actions work, exports, live dashboard refresh(WS) |
| Recommendations | Recommendation panels load, explanation paths remain visible, exports download, and recommendation job updates refresh through WebSockets. |
| Static pages | Privacy Policy, Terms of Service, contact |
| Console/network | Browser console has no app errors |

## Notes

- Warning for the local self-signed HTTPS certificate. 
- If a browser blocks popups, the user must allow the popup for the local site before export.
- WebSocket-backed dashboard and recommendation updates require the app to be opened through the gateway so the browser can use the correct `ws://` or `wss://` URL.
- Session data and theme preference are stored in browser's `localStorage`. Private browsing modes or strict storage settings can clear this data between sessions. Leftovers are possible from previous sessions.
- No intentional feature differences are defined between Chrome, Firefox, Safari, and Edge. Any rendering, interaction, export, or WebSocket difference found during manual testing should be treated as a bug and fixed before final evaluation.
