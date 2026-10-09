#!/bin/bash
# Vigila uno o varios kernels de Kaggle: escribe una línea cuando cambia su estado y, al terminar, las líneas clave del registro.
# Uso: ./vigilar_kernels.sh slug1 [slug2 …]   (cada línea que escribe es un evento para Monitor)
cd "$(dirname "$0")"
declare -A prev fin
slugs="${@:-$(python3 -c "import json,pathlib; print(json.load(open(pathlib.Path.home()/'.cache'/'vlm_profesor_kernel.json'))['slug'])")}"
while true; do
  todos=1
  for s in $slugs; do
    [ "${fin[$s]}" = "1" ] && continue
    out=$(python3 kaggle_ops.py estado $s 2>&1 | grep -v -i warn || true)
    st=$(echo "$out" | head -1)
    if [ "$st" != "${prev[$s]}" ]; then echo "$s: $st"; prev[$s]="$st"; fi
    case "$st" in
      *COMPLETE*|*ERROR*|*CANCEL*) echo "$out" | grep -E "LISTO|falló|Traceback|cargado en" | cut -c1-400 | tail -15; fin[$s]=1;;
      *) todos=0;;
    esac
  done
  [ "$todos" = "1" ] && break
  sleep 60
done
