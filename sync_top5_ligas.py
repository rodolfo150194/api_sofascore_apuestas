"""
Script para sincronizar SOLO las 5 grandes ligas europeas
- La Liga (España)
- Premier League (Inglaterra)
- Serie A (Italia)
- Bundesliga (Alemania)
- Ligue 1 (Francia)
"""

import asyncio
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sofascore_project.settings')
django.setup()

from poblar_bd_sofascore import SofascoreSyncManager
from futbol.models import Liga, Temporada, Partido

# Configuración de las 5 grandes ligas
TOP_5_LIGAS = {
    'laliga': {
        'nombre': 'La Liga',
        'tournament_id': 8,
        'temporadas': [
            {'season_id': 61643, 'nombre': 'LaLiga 24/25', 'year': '24/25'},
            {'season_id': 52376, 'nombre': 'LaLiga 23/24', 'year': '23/24'},
            {'season_id': 42409, 'nombre': 'LaLiga 22/23', 'year': '22/23'},
        ]
    },
    'premier': {
        'nombre': 'Premier League',
        'tournament_id': 17,
        'temporadas': [
            {'season_id': 61627, 'nombre': 'Premier League 24/25', 'year': '24/25'},
            {'season_id': 52186, 'nombre': 'Premier League 23/24', 'year': '23/24'},
            {'season_id': 41886, 'nombre': 'Premier League 22/23', 'year': '22/23'},
        ]
    },
    'seriea': {
        'nombre': 'Serie A',
        'tournament_id': 23,
        'temporadas': [
            {'season_id': 61644, 'nombre': 'Serie A 24/25', 'year': '24/25'},
            {'season_id': 52760, 'nombre': 'Serie A 23/24', 'year': '23/24'},
            {'season_id': 42415, 'nombre': 'Serie A 22/23', 'year': '22/23'},
        ]
    },
    'bundesliga': {
        'nombre': 'Bundesliga',
        'tournament_id': 35,
        'temporadas': [
            {'season_id': 61628, 'nombre': 'Bundesliga 24/25', 'year': '24/25'},
            {'season_id': 52608, 'nombre': 'Bundesliga 23/24', 'year': '23/24'},
            {'season_id': 42268, 'nombre': 'Bundesliga 22/23', 'year': '22/23'},
        ]
    },
    'ligue1': {
        'nombre': 'Ligue 1',
        'tournament_id': 34,
        'temporadas': [
            {'season_id': 61645, 'nombre': 'Ligue 1 24/25', 'year': '24/25'},
            {'season_id': 53525, 'nombre': 'Ligue 1 23/24', 'year': '23/24'},
            {'season_id': 42413, 'nombre': 'Ligue 1 22/23', 'year': '22/23'},
        ]
    }
}


async def sync_liga_completa_con_estadisticas(liga_config: dict, temporadas: list = None):
    """Sincronizar una liga completa con todas sus estadísticas"""
    manager = SofascoreSyncManager()

    try:
        nombre = liga_config['nombre']
        tournament_id = liga_config['tournament_id']
        temporadas_list = temporadas or liga_config['temporadas']

        print(f"\n{'=' * 70}")
        print(f"🏆 {nombre.upper()}")
        print(f"{'=' * 70}")

        for i, temp_info in enumerate(temporadas_list, 1):
            season_id = temp_info['season_id']
            temp_nombre = temp_info['nombre']

            print(f"\n📅 Temporada {i}/{len(temporadas_list)}: {temp_nombre}")
            print("-" * 70)

            # 1. Sincronizar liga y temporada
            torneo_data = await manager.api.get_torneo_info(tournament_id)
            liga = await manager.sync_liga(torneo_data.get('uniqueTournament', {}))

            try:
                season_data = await manager.api.get_info_temporada_info(tournament_id, season_id)
                temporada = await manager.sync_temporada(
                    season_data.get('info', {}).get('season', {}), liga
                )
            except:
                temporada = await manager.sync_temporada({
                    'id': season_id,
                    'name': temp_nombre,
                    'year': temp_info['year']
                }, liga)

            print(f"✓ Liga y temporada configuradas")

            # 2. Sincronizar equipos
            try:
                equipos_data = await manager.api.get_equipos_temporada_info(tournament_id, season_id)
                equipos = equipos_data.get('teams', [])
                print(f"✓ Sincronizando {len(equipos)} equipos...")

                for team_data in equipos:
                    equipo = await manager.sync_equipo(team_data.get('team', {}))
                    if equipo:
                        try:
                            await manager.sync_jugadores_equipo(equipo.sofascore_id, equipo)
                        except:
                            pass

                print(f"✓ Equipos y jugadores sincronizados")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠ Error con equipos: {str(e)[:50]}")

            # 3. Sincronizar TODOS los partidos
            try:
                partidos_data = await manager.api.get_torneo_partidos(tournament_id, season_id)
                eventos = partidos_data.get('events', [])

                # Obtener también próximos partidos
                try:
                    proximos_data = await manager.api.get_torneo_proximos_partidos(tournament_id, season_id)
                    eventos.extend(proximos_data.get('events', []))
                except:
                    pass

                print(f"✓ Sincronizando {len(eventos)} partidos...")

                sincronizados = 0
                con_detalles = 0

                for idx, evento in enumerate(eventos, 1):
                    try:
                        partido = await manager.sync_partido(evento)

                        if partido:
                            sincronizados += 1

                            # Sincronizar detalles si está finalizado
                            if partido.estado == 'finished':
                                try:
                                    await manager.sync_detalles_partido(partido.sofascore_id, partido)
                                    con_detalles += 1
                                except:
                                    pass

                            # Progreso cada 20 partidos
                            if idx % 20 == 0:
                                print(f"  Progreso: {idx}/{len(eventos)} ({con_detalles} con estadísticas)")
                                await asyncio.sleep(1)
                    except:
                        continue

                print(f"✓ Partidos sincronizados: {sincronizados}/{len(eventos)}")
                print(f"✓ Con estadísticas completas: {con_detalles}")

            except Exception as e:
                print(f"✗ Error sincronizando partidos: {str(e)[:100]}")

            if i < len(temporadas_list):
                await asyncio.sleep(3)

        print(f"\n{'=' * 70}")
        print(f"✅ {nombre} COMPLETADA")
        print(f"{'=' * 70}")

    finally:
        await manager.close()


async def sync_todas_las_ligas():
    """Sincronizar las 5 grandes ligas completas"""

    print("\n" + "=" * 70)
    print("🌍 SINCRONIZACIÓN TOP 5 LIGAS EUROPEAS")
    print("=" * 70)
    print("\nEsto sincronizará:")
    for key, liga in TOP_5_LIGAS.items():
        print(f"  • {liga['nombre']} ({len(liga['temporadas'])} temporadas)")

    confirmar = input("\n¿Continuar? Esto puede tardar 2-3 horas (s/n): ").strip().lower()

    if confirmar != 's':
        print("Operación cancelada")
        return

    inicio = asyncio.get_event_loop().time()

    for key, liga_config in TOP_5_LIGAS.items():
        await sync_liga_completa_con_estadisticas(liga_config)
        await asyncio.sleep(5)  # Pausa entre ligas

    fin = asyncio.get_event_loop().time()
    tiempo_total = (fin - inicio) / 60

    print("\n" + "=" * 70)
    print("🎉 SINCRONIZACIÓN COMPLETADA")
    print(f"⏱️  Tiempo total: {tiempo_total:.1f} minutos")
    print("=" * 70)

    # Mostrar resumen
    from futbol.utils import resumen_base_datos
    resumen = resumen_base_datos()

    print("\n📊 RESUMEN FINAL:")
    print(f"  Partidos totales: {resumen['partidos']['total']}")
    print(f"  Partidos finalizados: {resumen['partidos']['finalizados']}")
    print(f"  Con estadísticas: {resumen['estadisticas_partido']}")
    print(f"  Eventos: {resumen['eventos']}")
    print(f"  Jugadores: {resumen['jugadores']}")


async def sync_solo_temporada_actual():
    """Sincronizar solo la temporada actual de cada liga"""

    print("\n" + "=" * 70)
    print("🏆 SINCRONIZACIÓN TEMPORADA ACTUAL (24/25)")
    print("=" * 70)

    for key, liga_config in TOP_5_LIGAS.items():
        temporada_actual = [liga_config['temporadas'][0]]  # Solo la primera
        await sync_liga_completa_con_estadisticas(liga_config, temporada_actual)
        await asyncio.sleep(3)

    print("\n✅ Temporadas actuales sincronizadas")


async def sync_liga_especifica():
    """Sincronizar una liga específica"""

    print("\nSelecciona la liga:")
    print("1. La Liga")
    print("2. Premier League")
    print("3. Serie A")
    print("4. Bundesliga")
    print("5. Ligue 1")

    opcion = input("\nOpción (1-5): ").strip()

    liga_map = {
        '1': 'laliga',
        '2': 'premier',
        '3': 'seriea',
        '4': 'bundesliga',
        '5': 'ligue1'
    }

    if opcion not in liga_map:
        print("Opción inválida")
        return

    liga_key = liga_map[opcion]
    liga_config = TOP_5_LIGAS[liga_key]

    print(f"\n¿Cuántas temporadas sincronizar?")
    print(f"1. Solo temporada actual (24/25)")
    print(f"2. Últimas 2 temporadas")
    print(f"3. Todas (3 temporadas)")

    temp_opcion = input("\nOpción (1-3): ").strip()

    if temp_opcion == '1':
        temporadas = [liga_config['temporadas'][0]]
    elif temp_opcion == '2':
        temporadas = liga_config['temporadas'][:2]
    else:
        temporadas = liga_config['temporadas']

    await sync_liga_completa_con_estadisticas(liga_config, temporadas)


async def limpiar_otras_ligas():
    """Eliminar partidos de ligas que no sean las Top 5"""

    print("\n⚠️  ADVERTENCIA: Esto eliminará partidos de ligas fuera del Top 5")
    confirmar = input("¿Continuar? (s/n): ").strip().lower()

    if confirmar != 's':
        print("Operación cancelada")
        return

    from asgiref.sync import sync_to_async

    # IDs de las Top 5
    top5_ids = [config['tournament_id'] for config in TOP_5_LIGAS.values()]

    # Buscar ligas en BD
    @sync_to_async
    def get_ligas_top5():
        return list(Liga.objects.filter(sofascore_id__in=top5_ids).values_list('id', flat=True))

    @sync_to_async
    def eliminar_partidos_otras_ligas(top5_liga_ids):
        count = Partido.objects.exclude(liga_id__in=top5_liga_ids).delete()
        return count[0]

    ligas_top5_ids = await get_ligas_top5()
    eliminados = await eliminar_partidos_otras_ligas(ligas_top5_ids)

    print(f"✓ Eliminados {eliminados} partidos de otras ligas")


async def verificar_datos_top5():
    """Verificar datos de las Top 5 ligas"""
    from asgiref.sync import sync_to_async

    print("\n" + "=" * 70)
    print("📊 DATOS DE LAS TOP 5 LIGAS")
    print("=" * 70)

    for key, liga_config in TOP_5_LIGAS.items():
        tournament_id = liga_config['tournament_id']
        nombre = liga_config['nombre']

        @sync_to_async
        def get_liga_stats(tid):
            try:
                liga = Liga.objects.get(sofascore_id=tid)
                partidos = liga.partidos.count()
                finalizados = liga.partidos.filter(estado='finished').count()
                con_stats = liga.partidos.filter(tiene_estadisticas=True).count()
                temporadas = liga.temporadas.count()

                return {
                    'existe': True,
                    'partidos': partidos,
                    'finalizados': finalizados,
                    'con_stats': con_stats,
                    'temporadas': temporadas
                }
            except Liga.DoesNotExist:
                return {'existe': False}

        stats = await get_liga_stats(tournament_id)

        print(f"\n{nombre}:")
        if stats['existe']:
            print(f"  ✓ Temporadas: {stats['temporadas']}")
            print(f"  ✓ Partidos: {stats['partidos']} ({stats['finalizados']} finalizados)")
            print(f"  ✓ Con estadísticas: {stats['con_stats']}")
        else:
            print(f"  ✗ No sincronizada")


async def main():
    print("\n" + "=" * 70)
    print("⚽ SINCRONIZACIÓN TOP 5 LIGAS EUROPEAS")
    print("=" * 70)
    print("\nOpciones:")
    print("1. Sincronizar TODAS las ligas (3 temporadas c/u) - COMPLETO")
    print("2. Sincronizar solo temporada actual (24/25) de todas")
    print("3. Sincronizar una liga específica")
    print("4. Verificar datos actuales")
    print("5. Limpiar partidos de otras ligas")
    print("6. Salir")

    opcion = input("\nSelecciona opción (1-6): ").strip()

    if opcion == '1':
        await sync_todas_las_ligas()
    elif opcion == '2':
        await sync_solo_temporada_actual()
    elif opcion == '3':
        await sync_liga_especifica()
    elif opcion == '4':
        await verificar_datos_top5()
    elif opcion == '5':
        await limpiar_otras_ligas()
    elif opcion == '6':
        print("\nHasta luego!")
        return
    else:
        print("Opción inválida")


if __name__ == "__main__":
    asyncio.run(main())