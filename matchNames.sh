#!/bin/bash
# matchNames changeDir matchDir
for f in $(ls ${1})
do
  name="${f%%.*}"
  target=(${2}/${name}*.pdf)
  #mv $f ${target##*/}
  echo $f
  echo $name
  echo $target
  echo ${target##*/}
  echo "${1}$f" "${1}/${target##*/}"
  if [ -f "$target" ]; then
    mv "${1}/$f" "${1}/${target##*/}" ;
  fi
done
