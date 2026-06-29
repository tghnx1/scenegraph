# Browser Support Documentation

Tests on:

- Chrome (version: 149.0.7872.155 & 149.0.7827.114)
- Firefox (version: 152.0.1 & 152.0)
- Edge (149.0.4022.98)
- Brave (1.91172)
- Mobile (via chrome. functional)

Use:

```bash
make upd-build
```

Then open:

```text
https://localhost:8443
```
## Aim
- The main aim is to make sure that all functionality works on all tested browser(s). 

## Tests

| Area |Verify |
| --- | --- |
| App shell | Home/graph page loads, navigation, theme styling, layout overlap (mobile may have this)|
| Authentication | Register, log in, log out. |
| Graph | Graph canvas: zoom/drag/click interactions work, filters update the visible graph, and the details panel. |
| Search | Search input, keyboard interaction, filters, selected result|
| Dashboard | Loads metrics, user-management actions work, exports, live dashboard refresh(WS) |
| Recommendations | Recommendation panels load, explanation paths remain visible, exports download, and recommendation job updates refresh through WebSockets. |
| Static pages | Content displayed |
| Console/network | Browser console errors |

## Notes

- Warning for the local self-signed HTTPS certificate.
- Session data and theme preference are stored in browser's `localStorage`. Private browsing modes or strict storage settings can clear this data between sessions. Leftovers are possible from previous sessions.
- No intentional feature differences are defined between Chrome, Firefox, Edge, and Brave.
- Brave browser's finger printing functionality interferes with the graph interaction. Disable it. No functionality can be observed to be hindered.
- Edge: No functionality can be observed to be hindered.
- Chrome: No functionality can be observed to be hindered.
- Firefox: No functionality can be observed to be hindered.