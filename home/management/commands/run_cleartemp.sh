# run_cleartemp.sh

#!/bin/bash

# Activar el entorno conda
conda activate test

python /hadoop/PruebasFileManager/sample-django-file-manager/manage.py cleartemp

conda deactivate
