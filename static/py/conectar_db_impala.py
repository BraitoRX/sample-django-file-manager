import pandas as pd
from impala.dbapi import connect

def executeQuery(query, table):
    HIVE_HS2_HOST = 'hadoop-dn1.fiscalia.col'
    
    print(f"Conectando a Hive en {HIVE_HS2_HOST}...")
    conn = connect(host=HIVE_HS2_HOST,
                   port=21050,
                   auth_mechanism='NOSASL',
                   kerberos_service_name='hive',               
                   )
    print("Conexión establecida.")

    cursor_hive = conn.cursor()
    cursor_hive.execute('USE target_spoa')
    print("Usando base de datos target_spoa.")

    def fetch_data(query):
        print(f"Ejecutando consulta: {query}")
        cursor_hive.execute(query)
        data = cursor_hive.fetchall()
        columns = [desc[0] for desc in cursor_hive.description]
        df = pd.DataFrame(data, columns=columns)
        print(f"Datos obtenidos: {len(df)} registros.")
        print(f"Estructura del DataFrame:\n{df.head()}")  # Mostrar los primeros 5 registros por defecto
        return df
        
    dfs = {}
    record_counts = {}
    df = fetch_data(query)
    dfs[table] = df
    record_counts[table] = len(df)

    print(f"DataFrame para {table} almacenado.")
    print(f"Cantidad de registros en {table}: {record_counts[table]}")
     
    return dfs, record_counts


def executeQueryComp(query):
    HIVE_HS2_HOST = 'hadoop-dn1.fiscalia.col'
    
    print(f"Conectando a Hive en {HIVE_HS2_HOST}...")
    conn = connect(host=HIVE_HS2_HOST,
                   port=21050,
                   auth_mechanism='NOSASL',
                   kerberos_service_name='hive',               
                   )
    print("Conexión establecida.")

    cursor_hive = conn.cursor()
    cursor_hive.execute('USE target_spoa')
    print("Usando base de datos target_spoa.")

    print(f"Ejecutando consulta: {query}")
    cursor_hive.execute(query)
    data = cursor_hive.fetchall()
    columns = [desc[0] for desc in cursor_hive.description]
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Datos obtenidos: {len(df)} registros.")
    print(f"Estructura del DataFrame:\n{df.head()}")  # Mostrar los primeros 5 registros por defecto
    
    cursor_hive.close()
    conn.close()
    
    return df