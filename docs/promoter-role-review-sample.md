# Promoter role review sample

These examples come from the production read-only audit. Expected roles below are
review hypotheses, not a completed ground-truth dataset. RA promoter IDs remain
source identities even where two profiles may represent the same organization.

| RA event | Evidence | Expected review outcome |
| --- | --- | --- |
| 2416601 | “Romantic Fiction & 8MM present Lila Ehjä Live”; RA promoters 184976 and 124478 | Retain both as organizers; 8MM is also the venue. |
| 1959762 | DUALISM event; ://about blank (13285), About Blank (8367), DUALISMBERLIN (108108) | Retain DUALISMBERLIN; review the two venue-matching profiles as potential aliases and venue credits. |
| 2010949 | LOWKEY STARS; ://about blank (13285), About Blank (8367), LOWKEY (149712) | Retain LOWKEY; review venue profiles as potential aliases and venue credits. |
| 2267598 | saHHara x Tag der Clubkultur; CrackBellmer (168546), Crack Bellmer (48504), saHHara (135300) | Retain saHHara; review the two venue-matching profiles as potential aliases and venue credits. |
| 2527382 | STAY CORE; CrackBellmer (168546), Crack Bellmer (48504) | Do not infer an independent promoter solely from the two profiles; their equivalence needs confirmation. |
| 2458034 | KOROWA at 8MM Bar; 8MM (124478), STEEL Rovinj (89404) | Review each organizer role using the event description; the title alone does not establish both roles. |

The reviewed production aggregate contained 25,435 events, 4,169 promoters,
1,671 venues, and 23,837 event-promoter links. This snapshot is not a baseline
of affected recommendation results; that measurement still needs to be made.
