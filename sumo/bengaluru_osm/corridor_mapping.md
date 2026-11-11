# Bengaluru OSM corridor mapping

## Source and coverage

The preserved OSM extract declares WGS84 bounds `77.567,12.882,77.693,12.958` (west,south,east,north). SUMO reports network `origBoundary` `77.512775,12.819088,77.782362,13.028218`; complete road shapes extend beyond the declared extract rectangle because OSM way geometry extends outside it. The corridor anchors below fall within the declared bounds. The wider network boundary is the proper extent when describing converted coverage.

Two separate conversions are retained: `bengaluru_osm.net.xml` is the original import and `bengaluru_osm_sim.net.xml` is the left-hand traffic simulation variant. Neither touches the original synthetic network. The simulation variant has 98,863 non-internal edges, 104,036 non-internal lanes, 43,936 non-internal junctions, and 554 traffic-light controllers. It was created with `--lefthand --tls.guess-signals --tls.guess-signals.dist 25 --tls.join`. The OSM extract has 428 `highway=traffic_signals` nodes. Converted signal phases and durations are SUMO-generated static plans; no field timings were supplied or validated. The conversion log records skipped zero-lane links, unresolved/ignored restrictions, sharp turns, connection speed adjustments, unavailable PT relation data and malformed widths defaulted; conversion ended with `Success` and no fatal error.

## Locality anchors and nearest drivable roads

Place labels are not treated as road or junction IDs. Candidate OSM features were spatially mapped to nearby passenger-accessible SUMO edges, and route connectivity was then checked in the simulation network.

| Anchor | OSM feature | OSM node ID | WGS84 | SUMO edge | Road name | Distance |
|---|---|---:|---|---|---|---:|
| Silk Board | named bus-stop feature | `1723812996` | `12.9167972,77.6235628` | `1208112310#1` | unnamed edge beside Silk Board Interchange/Flyover | 2.5 m |
| HSR Layout | `place=suburb` marker | `456016994` | `12.9116225,77.6388622` | `-133945864` | 19th Cross Road | 18.4 m |
| Koramangala | `place=suburb` marker | `429918282` | `12.9357366,77.6240810` | `558765859#3` | 17th A Main Road | 19.8 m |

Distances are nearest-edge geometry distances, not junction connections. The Silk Board marker is a bus stop beside the interchange, not the junction itself. All chosen edges are passenger-accessible and exist in the left-hand simulation conversion.

## Directed corridor routes

The route generator recomputes these passenger shortest paths from the simulation network at run time. The six paths use mapped roads and connected intersections, not a generated grid.

| OD | Length | Directed edges |
|---|---:|---:|
| Silk Board → HSR Layout | 1,932.9 m | 51 |
| HSR Layout → Silk Board | 1,718.2 m | 55 |
| HSR Layout → Koramangala | 3,176.2 m | 143 |
| Koramangala → HSR Layout | 3,204.0 m | 113 |
| Silk Board → Koramangala | 2,327.1 m | 64 |
| Koramangala → Silk Board | 3,290.9 m | 101 |

Each selected corridor path allows passenger, motorcycle, bus and truck classes. The route generator validates permission on every edge for all five archetypes and errors instead of silently forcing an inaccessible vehicle. The previous base network analysis found 67 weakly connected passenger components (largest 75,956 edges); the chosen corridor paths are in a connected component. This does not make all roads in the extract connected or usable.

Thirty-five TLS IDs have controlled links on at least one selected corridor route. The nearest OSM signal nodes at place markers can control only straight continuation links, so proximity alone is not a control suitability test. Dynamic control is limited to corridor-route TLSs and preserves their phase order; adaptive logic only extends a currently green phase. Before expanded controller experiments, inspect signal grouping and movements individually. Generated timing plans are assumptions, not actual Bengaluru signal timings.

## Historical data correspondence

The historical CSV has eight area labels and 16 road/intersection labels. `Hosur Road` and `Sarjapur Road` are candidate road-name matches to nearby OSM road names (`Sarjapura Road` occurs in OSM); `Silk Board Junction` is a likely place/interchange correspondence, not an edge. `Koramangala` appears as an area label. Thirteen of 16 road/intersection labels do not have a defensible exact named-road match in this study corridor. No daily traffic count is assigned to a road edge or converted to a vehicle arrival rate: the dataset does not document the count units, hourly profiles, OD, trajectories, actual fleet composition, queue lengths or signal timing plans. All demonstration demand rates and vehicle shares are labeled assumptions.
