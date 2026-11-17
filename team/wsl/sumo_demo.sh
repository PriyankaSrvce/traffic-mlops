#!/usr/bin/env bash
# Open SUMO's map window and run a signal controller on the Bengaluru corridor (low demand,
# seed 123). "predictive" uses the production model. The window opens after 30-60 s.
# Usage: sumo_demo.sh [predictive|adaptive|fixed]     SUMO_DEMO_HEADLESS=1 runs without a window.
. "$(dirname "$0")/common.sh"
need_venv
POLICY="${1:-predictive}"
NET=sumo/bengaluru_osm/bengaluru_osm_sim.net.xml
[ -f "$NET" ] || fail "Missing $NET. Run team/windows/1_GET_DATA.cmd first."
export SUMO_HOME="$("$PY" -c 'import sumo; print(sumo.SUMO_HOME)')"
D="$OUT/sumo_demo"; mkdir -p "$D"
ROUTES="$D/routes_low_seed123.rou.xml"
[ -f "$ROUTES" ] || "$PY" sumo/bengaluru_osm/generate_scenario.py --scenario low --seed 123 --duration 900 --output "$ROUTES" >/dev/null

if [ "${SUMO_DEMO_HEADLESS:-0}" = 1 ]; then
  SUMO_BIN="$VENV/bin/sumo"
else
  # WSLg sometimes loses its display link after Ubuntu starts; repair it if possible.
  if [ ! -e /tmp/.X11-unix/X0 ] && [ -S /mnt/wslg/.X11-unix/X0 ]; then
    ln -sf /mnt/wslg/.X11-unix/X0 /tmp/.X11-unix/X0 2>/dev/null || true
  fi
  [ -e /tmp/.X11-unix/X0 ] || fail "No WSL display. In PowerShell run:  wsl --shutdown   then try again (needs Windows 11 / WSLg)."
  SUMO_BIN="$D/sumo-gui-start"
  printf '#!/usr/bin/env bash\nexec "%s" --start --gui-settings-file "%s" "$@"\n' \
    "$VENV/bin/sumo-gui" "$REPO/team/sumo/gui-settings.xml" > "$SUMO_BIN"
  chmod +x "$SUMO_BIN"
fi

MODEL="$(production_model)"
say "Starting SUMO with the $POLICY controller"
"$PY" sumo/bengaluru_osm/controller.py --policy "$POLICY" --scenario low --seed 123 \
  --routes "$ROUTES" --model "$MODEL" --metadata src/api/bengaluru_deployment_metadata.json \
  --sumo "$SUMO_BIN" --log "$D/${POLICY}_decisions.csv" --tripinfo "$D/${POLICY}_tripinfo.xml"
echo "Signal decisions saved to outputs/sumo_demo/${POLICY}_decisions.csv"
finish
