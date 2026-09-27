#!/bin/bash
# Download all SRTM 1-arcsec HGT tiles covering Chhattisgarh state, India.
# Chhattisgarh extent: ~17.8°N–24.1°N, ~80.2°E–84.4°E
# Tiles: N17–N23, E080–E084 (35 tiles, ~25MB each uncompressed from AWS)
# AWS S3 skadi bucket: no auth required, reliable.
#
# Usage: bash download_srtm_tiles.sh
# Run from repo root. Places tiles in backend/app/data/srtm/

set -e
DEST="backend/app/data/srtm"
mkdir -p "$DEST"

LATS="17 18 19 20 21 22 23"
LONS="80 81 82 83 84"

echo "=== Downloading SRTM tiles for Chhattisgarh ==="
COUNT=0
SKIP=0

for LAT in $LATS; do
  for LON in $LONS; do
    TILE="N${LAT}E0${LON}"
    HGT="$DEST/${TILE}.hgt"

    if [ -f "$HGT" ]; then
      echo "  SKIP  $TILE (already exists, $(du -h "$HGT" | cut -f1))"
      SKIP=$((SKIP+1))
      continue
    fi

    URL="https://s3.amazonaws.com/elevation-tiles-prod/skadi/N${LAT}/${TILE}.hgt.gz"
    GZ="${HGT}.gz"

    echo -n "  GET   $TILE ... "
    if curl --interface wlp1s0 -sf --max-time 90 -o "$GZ" "$URL" 2>/dev/null; then
      gunzip -f "$GZ"
      SIZE=$(du -h "$HGT" | cut -f1)
      echo "OK ($SIZE)"
      COUNT=$((COUNT+1))
    else
      echo "FAIL (tile may not exist or network error)"
    fi
  done
done

echo ""
echo "=== Done: $COUNT downloaded, $SKIP skipped ==="
echo "Tiles in $DEST:"
ls -lh "$DEST"/*.hgt 2>/dev/null | awk '{print "  "$5, $9}' || echo "  (none)"
