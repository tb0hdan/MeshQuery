# TODO items

- [] implement pagination for packets, nodes, trace route pages ideally, nodes should be able to fit all nodes in under 10 pages.
     User should be able to set amount of line per page dropdown, 5 - 100. Packets should probably be limited to 1000 latest to be searchable there.

- [] The map page has a node (or cluster if the node is inside) flash green for transmission, red for receptions.
     The animations are a bit weird and hard to notice, we should ask  claude to enhance it.

- [] Hop analysis and gateway compare - utterly broken at the moment / useless pages

- [] longest links - broken completely [see below about tier b pipeline / materialized view]

- [] Packet heatmap - this look fine but the circles of node shading could be larger even when zoomed (weird zoom issues)

- [] Live Topography needs a bunch of work, animations dont really happen right, trace route with hops above needs fixing ect.

- [] MQTT packets show trails on live and map sometimes, ive asked it to globally limit RF rendered lines and animations to be under 150km 
     to be considered real (unless it has valid, normal range SNR / RSSI values, probably broken)

- [] The Light/Dark theme toggle is borked. Way upstream, original author of malla has already done a commit on this, could look there.

- [] The postgres - > webui is fast but the api / backend db handling is really borked.

- [] There is duplicate/useless functions and pages that never panned out and are dangling. 
     Earlier it created this Tier B pipeline to handle extracting hops / information for faster processing of long links page and other things,
     this is a major headache for everything and should be refactored out / replaced into a more robust single endpoint solution for this stuff.

- [] the schema, its a mess, same about about migrations.
