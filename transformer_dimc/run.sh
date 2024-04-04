#!/bin/bash

declare -a arr=("KQV", "KTQ", "VScores", "Out", "FF1", "FF2")

for i in "${arr[@]}"
do
   printf "\n\n--------------------
WORKING ON: $i
--------------------\n\n"
   mkdir "outputs_$i"
   sudo timeloop-mapper *.yaml "problems/${i}_layer.yaml" -o "./outputs_$i"
   printf "\n\n--------------------
MAPPING FOR: $i
--------------------\n\n"
   cat "outputs_$i/timeloop-mapper.map.txt"
   printf "\n\n"
done

printf "\n\n!! --> DONE <-- !!\n\n"

exit