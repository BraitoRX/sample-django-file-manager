import os
import uuid
import csv
from django.shortcuts import render, redirect
from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from home.models import FileInfo
from django.core.paginator import Paginator
import tempfile
from hdfs3 import HDFileSystem
from django.shortcuts import render
from django.core.cache import cache
import mimetypes
from static.py.conectar_db_impala import executeQueryComp
# Create your views here.

def index(request):
    return redirect('file_manager')




def convert_csv_to_text(csv_file_path):
    with open(csv_file_path, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)

    text = ''
    for row in rows:
        text += ','.join(row) + '\n'
    return text

def show_text_file(absolute_file_path):
    with open(absolute_file_path, 'r') as file:
      # Lee el contenido del archivo
      content = file.read()
      # Prepara la respuesta HTTP con el contenido del archivo
      response = HttpResponse(content, content_type="text/plain")
    return response



    

def get_files_from_directory_hdfs(hdfs, directory):
    """
    List files and directories in a given HDFS directory with details.

    Args:
    hdfs (HDFileSystem): An instance of HDFileSystem to interact with HDFS.
    directory (str): The directory path in HDFS to list.

    Returns:
    tuple: Two lists, the first containing dictionaries of file details,
           the second containing names of directories.
    """
    entries = hdfs.ls(directory, detail=True)
    files = []
    directories = []
    for entry in entries:
        if entry['kind'] == 'file':
            full_path = entry['name']
            filename = os.path.basename(full_path)
            file_extension = os.path.splitext(filename)[1]
            files.append({
                'file': full_path,
                'filename': filename,
                'file_extension': file_extension
            })
        elif entry['kind'] == 'directory':
            directories.append({"name": os.path.basename(entry['name'])})
    return files, directories



    
def generate_nested_directory_hdfs(hdfs, root_path, current_path):
  directories = []
  try:
    # Listar el contenido del directorio actual en HDFS
    for file_info in hdfs.ls(current_path, detail=True):
      if file_info['kind'] == 'directory':
        unique_id = str(uuid.uuid4())
        name = file_info['name'].split('/')[-1]  # Obtener el nombre del directorio
        nested_path = file_info['name']
        # Llamada recursiva para explorar el contenido de este directorio
        nested_directories = generate_nested_directory_hdfs(hdfs, root_path, nested_path)
        # Añadir este directorio a la lista, incluyendo sus subdirectorios
        directories.append({
                    'id': unique_id,
                    'name': name,
                    'path': nested_path[len(root_path):] if nested_path.startswith(root_path) else nested_path,
                    'directories': nested_directories
                })
  except Exception as e:
    print(f'Error al listar directorios desde HDFS: {str(e)}')
    
  return directories



def get_files_from_directory(directory_path):
    files = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isfile(file_path):
            try:
                print( ' > file_path ' + file_path)
                _, extension = os.path.splitext(filename)
                if extension.lower() == '.csv':
                    csv_text = convert_csv_to_text(file_path)
                else:
                    csv_text = ''

                files.append({
                    'file': file_path.split(os.sep + 'media' + os.sep)[1],
                    'filename': filename,
                    'extension': extension,
                    'file_path': file_path,
                    'csv_text': csv_text
                })
            except Exception as e:
                print( ' > ' +  str( e ) )    
    return files

def save_info(request, file_path):
    path = file_path.replace('%slash%', '/')
    if request.method == 'POST':
        FileInfo.objects.update_or_create(
            path=path,
            defaults={
                'info': request.POST.get('info')
            }
        )
    
    return redirect(request.META.get('HTTP_REFERER'))

def get_breadcrumbs(request):
    path_components = [component for component in request.path.split("/") if component]
    breadcrumbs = []
    url = ''

    for component in path_components:
        url += f'/{component}'
        if component == "file-manager":
            component = "media"
        breadcrumbs.append({'name': component, 'url': url})

    return breadcrumbs

def organizar_directorios_archivos(archivos, directorios, hdfs, temp_dir_path, request,initial_path="/"):

    paginator = Paginator(archivos, 20)
    page_number = request.GET.get('page', 1)  
    page_obj = paginator.get_page(page_number)  

    for archivo in archivos:
        local_file_name = os.path.basename(archivo['file'])
        path = os.path.join(initial_path, local_file_name)
        archivo["path"] = path

        if archivo['file_extension'] in [".png",".jpg",".jpeg",".gif"]:
            file_extension = archivo['file_extension']
            absolute_file_path = os.path.join(temp_dir_path, local_file_name)
            hdfs.get(archivo['file'], absolute_file_path)
            relative_file_path = os.path.join('Temp', local_file_name)
            archivo['temp'] = relative_file_path

            

    paginator_dir = Paginator(directorios, 5)
    paginator_page_number_dir = request.GET.get('page_dir', 1)  
    page_obj_dir = paginator_dir.get_page(paginator_page_number_dir)  

    for directorio in directorios:
        path = os.path.join(initial_path, directorio['name'])
        directorio['path'] = path
    return archivos, directorios, page_obj_dir, page_obj


def file_manager(request, file_path=None, directory=None):
    hdfs = HDFileSystem(host='hadoop-ann1.fiscalia.col', port=8020)

    # Crear el directorio 'Temp' dentro de MEDIA_ROOT si no existe
    temp_dir_path = os.path.join(settings.MEDIA_ROOT, 'Temp')
    if not os.path.exists(temp_dir_path):
        os.makedirs(temp_dir_path)

    # Si no hay una ruta de archivo especificada, muestra el directorio raíz
    if file_path is None or directory:
        archivos, directorios = get_files_from_directory_hdfs(hdfs, "/")
        archivos, directorios, page_obj_dir, page_obj = organizar_directorios_archivos(archivos, directorios, hdfs, temp_dir_path, request)
        return render(request, 'pages/file-manager.html', {
            'directories': directorios,
            "page_obj_dir": page_obj_dir,
            'selected_directory': "/",
            'page_obj': page_obj,
            'segment': 'file_manager'
        })
    else:
        normalized_file_path = file_path.replace('%slash%', '/')
        try:
            file_info = hdfs.info(normalized_file_path)
        except FileNotFoundError:
            raise Http404('El archivo o directorio solicitado no existe.')
        
        if file_info['kind'] == 'directory':
            archivos, directorios = get_files_from_directory_hdfs(hdfs, normalized_file_path)
            archivos, directorios, page_obj_dir, page_obj = organizar_directorios_archivos(archivos, directorios, hdfs, temp_dir_path, request, normalized_file_path)
            return render(request, 'pages/file-manager.html', {
                'directories': directorios,
                "page_obj_dir": page_obj_dir,
                'selected_directory': normalized_file_path,
                'page_obj': page_obj,
                'segment': 'file_manager'
            })
        else:
            local_file_name = os.path.basename(normalized_file_path)
            file_extension = os.path.splitext(local_file_name)[1].lower()
            absolute_file_path = os.path.join(temp_dir_path, local_file_name)

            hdfs.get(normalized_file_path, absolute_file_path)
            os.utime(absolute_file_path, None)
            
            relative_file_path = os.path.join('Temp', local_file_name)

            parent_directory = os.path.dirname(normalized_file_path)
            parent_directory_name = os.path.basename(parent_directory)

            try:
                supported_extensions = [
                    '.txt', '.csv', '.pdf', '.png', '.jpg', '.jpeg', '.mp4', '.mp3', '.wav', '.opus', '.ogg', '.m4a',
                    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp', '.rtf'
                ]
                
                if file_extension in supported_extensions:
                    return render(request, 'pages/file-manager.html', {
                        'file_path': normalized_file_path,
                        'temp': relative_file_path,
                        'file_name': local_file_name,
                        'csv_text': None if file_extension != '.csv' else convert_csv_to_text(absolute_file_path),
                        'file_extension': file_extension,
                        'parent_directory': parent_directory,
                        'parent_directory_name': parent_directory_name
                    })
                else:
                    return HttpResponse('Formato de archivo no soportado.', status=415)
            except IOError:
                return HttpResponse('Error al abrir o leer el archivo.', status=500)

def generate_nested_directory(root_path, current_path):
    directories = []
    for name in os.listdir(current_path):
        if os.path.isdir(os.path.join(current_path, name)):
            unique_id = str(uuid.uuid4())
            nested_path = os.path.join(current_path, name)
            nested_directories = generate_nested_directory(root_path, nested_path)
            directories.append({'id': unique_id, 'name': name, 'path': os.path.relpath(nested_path, root_path), 'directories': nested_directories})
    return directories


def delete_file(request, file_path):
    path = file_path.replace('%slash%', '/')
    absolute_file_path = os.path.join(settings.MEDIA_ROOT, path)
    os.remove(absolute_file_path)
    print("File deleted", absolute_file_path)
    return redirect(request.META.get('HTTP_REFERER'))

    
def upload_file(request):
    media_path = os.path.join(settings.MEDIA_ROOT)
    selected_directory = request.POST.get('directory', '') 
    selected_directory_path = os.path.join(media_path, selected_directory)
    if request.method == 'POST':
        file = request.FILES.get('file')
        file_path = os.path.join(selected_directory_path, file.name)
        with open(file_path, 'wb') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

    return redirect(request.META.get('HTTP_REFERER'))






def file_detail(request, file_path=None):
    if file_path is None:
        archivos = get_files_from_directory(settings.MEDIA_ROOT)
        return render(request, 'pages/file_detail.html', {
            'files': archivos, 
            'selected_files': request.session.get('selected_files', []),
            'parent_directory': None,
            'parent_directory_name': "Directorio raíz"
        })
    
    else:
        file_path = file_path.replace('%slash%', '/')
        absolute_file_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, file_path))

        if not os.path.exists(absolute_file_path):
            raise Http404

        file_name = os.path.basename(file_path)
        parent_directory = os.path.dirname(file_path)
        parent_directory_name = os.path.basename(parent_directory) if parent_directory else "Directorio raíz"

        if os.path.isfile(absolute_file_path):
            csv_text = ''
            if file_name.endswith('.csv'):
                csv_text = convert_csv_to_text(absolute_file_path)

            return render(request, 'pages/file_detail.html', {
                'file_path': file_path, 
                'file_name': file_name, 
                'csv_text': csv_text, 
                'file_extension': os.path.splitext(file_name)[1],
                'selected_files': request.session.get('selected_files', []),
                'parent_directory': parent_directory,
                'parent_directory_name': parent_directory_name
            })
        
        if os.path.isdir(absolute_file_path):
            absolute_files = get_files_from_directory(absolute_file_path)

        return render(request, 'pages/file_detail.html', {
            'files': absolute_files, 
            'selected_files': request.session.get('selected_files', []),
            'parent_directory': parent_directory,
            'parent_directory_name': parent_directory_name
        })


def view_selected_files(request):
    if request.method == 'POST':
        selected_files = request.POST.getlist('selected_files')
        current_directory = request.POST.get('current_directory', '/')
        
        if 'selected_files' not in request.session:
            request.session['selected_files'] = []
        
        request.session['selected_files'] = list(set(request.session['selected_files'] + selected_files))
        request.session.modified = True
        
        file_details = []
        for file_path in request.session['selected_files']:
            file_name = file_path.split('/')[-1]
            file_extension = file_name.split('.')[-1].upper()
            file_details.append({
                'path': file_path,
                'name': file_name,
                'extension': file_extension
            })
        
        return_directory = current_directory
        return_directory_name = os.path.basename(current_directory) if current_directory != '/' else "Directorio raíz"
        
        return render(request, 'pages/view_selected_files.html', {
            'file_details': file_details,
            'return_directory': return_directory,
            'return_directory_name': return_directory_name
        })
    else:
        return redirect('file_manager')
        
def clear_session(request):
    request.session.flush()
    return redirect('file_manager')


import pandas as pd
from impala.dbapi import connect
from urllib.parse import unquote
from django.http import JsonResponse

def get_ruta_destino(request, charla, no_caso, no_prueba, ambiente):
    query = f"""
    SELECT id, charla, adjunto, ruta_metadata, ruta_destino, transcripcion, clasificacion, no_caso, no_prueba, ambiente
    FROM transit_analisisforense.adjuntos_ext_ufdr
    WHERE charla='{charla}' AND no_caso='{no_caso}' AND no_prueba='{no_prueba}' AND ambiente='{ambiente}'
    """
    
    df = executeQueryComp(query)
    
    if df.empty:
        return JsonResponse({"error": "No se encontraron resultados para los parámetros proporcionados."}, status=404)
    
    # Extraer las rutas de destino completas
    rutas_destino = df['ruta_destino'].apply(lambda x: unquote(x) if pd.notnull(x) else None).tolist()
    
    return JsonResponse({"rutas_destino": rutas_destino})



