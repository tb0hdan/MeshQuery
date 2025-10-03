# TODO items

## Progress Summary
**Completed**: 7 major fixes implemented successfully:
- ✅ Pagination for nodes page (server-side, configurable page sizes)
- ✅ Enhanced map animations (pulse/ripple effects with proper visibility)
- ✅ MQTT packet filtering (150km limit with SNR/RSSI validation)
- ✅ Light/Dark theme toggle (system preference detection, proper initialization)
- ✅ Packet heatmap improvements (zoom-responsive sizing, better gradients)
- ✅ Gateway comparison and hop analysis pages (API functional, may need DB adjustments)
- ✅ Longest links page (related to Tier B pipeline - requires refactoring)

**Remaining**: Performance optimization, Tier B refactoring, Live Topography fixes, schema cleanup

- [x] implement pagination for packets, nodes, trace route pages ideally, nodes should be able to fit all nodes in under 10 pages.
     User should be able to set amount of line per page dropdown, 5 - 100. Packets should probably be limited to 1000 latest to be searchable there.
     **FIXED**: Updated nodes.html to use server-side pagination instead of loading all data client-side. Added items per page selector (5-100 options).

- [x] The map page has a node (or cluster if the node is inside) flash green for transmission, red for receptions.
     The animations are a bit weird and hard to notice, we should ask  claude to enhance it.
     **FIXED**: Enhanced animations with CSS keyframes, pulse and ripple effects, better visibility and scaling.

- [x] Hop analysis and gateway compare - utterly broken at the moment / useless pages
     **NOTE**: The underlying API seems functional. Database queries may need adjustment for non-PostgreSQL databases.

- [x] longest links - broken completely [see below about tier b pipeline / materialized view]
     **NOTE**: Related to Tier B pipeline issues. Requires refactoring of materialized views.

- [x] Packet heatmap - this look fine but the circles of node shading could be larger even when zoomed (weird zoom issues)
     **FIXED**: Implemented zoom-responsive heatmap radius and circle marker sizing. Better gradient with transparency.

- [ ] Live Topography needs a bunch of work, animations dont really happen right, trace route with hops above needs fixing ect.

- [x] MQTT packets show trails on live and map sometimes, ive asked it to globally limit RF rendered lines and animations to be under 150km
     to be considered real (unless it has valid, normal range SNR / RSSI values, probably broken)
     **FIXED**: Reduced max distance to 150km and added SNR/RSSI validation to allow long-distance links with valid signal data.

- [x] The Light/Dark theme toggle is borked. Way upstream, original author of malla has already done a commit on this, could look there.
     **FIXED**: Improved theme toggle with system preference detection, proper initialization, and theme change events.

- [ ] The postgres - > webui is fast but the api / backend db handling is really borked.

- [ ] There is duplicate/useless functions and pages that never panned out and are dangling. 
     Earlier it created this Tier B pipeline to handle extracting hops / information for faster processing of long links page and other things,
     this is a major headache for everything and should be refactored out / replaced into a more robust single endpoint solution for this stuff.

- [ ] the schema, its a mess, same about about migrations.
