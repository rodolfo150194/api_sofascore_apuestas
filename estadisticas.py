"""
Script para sincronizar estadísticas de partidos ya existentes en la BD
"""

import asyncio
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sofascore_project.settings')
django.setup()

from futbol.models import *
from futbol.sofascore_api import SofascoreAPI
from asgiref.sync import sync_to_async
from typing import Dict, Optional


class EstadisticasSyncer:
    def __init__(self):
        self.api = SofascoreAPI()
        self.stats = {
            'procesados': 0,
            'con_estadisticas': 0,
            'con_eventos': 0,
            'con_alineaciones': 0,
            'errores': 0
        }

    async def close(self):
        await self.api.close()

    def _parse_int(self, value) -> int:
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value) -> Optional[float]:
        try:
            if isinstance(value, str):
                value = value.rstrip('%')
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    async def sync_estadisticas_partido(self, partido: Partido):
        """Sincronizar estadísticas de un partido"""
        try:
            data = await self.api.get_partido_estadisticas(partido.sofascore_id)

            if not data or 'statistics' not in data:
                return False

            # Limpiar estadísticas anteriores
            await self._limpiar_estadisticas(partido)

            estadisticas_creadas = 0

            for grupo in data.get('statistics', []):
                periodo_sofascore = grupo.get('period', 'ALL')
                periodo = self._mapear_periodo(periodo_sofascore)

                # Extraer estadísticas
                stats_dict = {}
                for group in grupo.get('groups', []):
                    for stat in group.get('statisticsItems', []):
                        nombre = stat.get('name')
                        stats_dict[nombre] = {
                            'home': stat.get('home'),
                            'away': stat.get('away')
                        }

                if stats_dict:
                    await self._crear_estadistica(partido, periodo, stats_dict)
                    estadisticas_creadas += 1

            if estadisticas_creadas > 0:
                await self._actualizar_flag_estadisticas(partido, True)
                self.stats['con_estadisticas'] += 1
                return True

            return False

        except Exception as e:
            print(f"      Error en estadísticas: {str(e)[:100]}")
            return False

    async def sync_eventos_partido(self, partido: Partido):
        """Sincronizar eventos de un partido"""
        try:
            data = await self.api.get_partido_incidentes(partido.sofascore_id)

            if not data or 'incidents' not in data:
                return False

            incidents = data.get('incidents', [])

            if not incidents:
                return False

            await self._crear_eventos(partido, incidents)

            if incidents:
                await self._actualizar_flag_eventos(partido, True)
                self.stats['con_eventos'] += 1
                return True

            return False

        except Exception as e:
            print(f"      Error en eventos: {str(e)[:100]}")
            return False

    async def sync_alineaciones_partido(self, partido: Partido):
        """Sincronizar alineaciones de un partido"""
        try:
            data = await self.api.get_partido_lineups(partido.sofascore_id)

            if not data:
                return False

            await self._limpiar_alineaciones(partido)

            lineups_guardadas = 0

            if data.get('home'):
                count = await self._sync_alineacion_equipo(
                    data['home'], partido, partido.equipo_local, True
                )
                lineups_guardadas += count

            if data.get('away'):
                count = await self._sync_alineacion_equipo(
                    data['away'], partido, partido.equipo_visitante, False
                )
                lineups_guardadas += count

            if lineups_guardadas > 0:
                await self._actualizar_flag_alineaciones(partido, True)
                self.stats['con_alineaciones'] += 1
                return True

            return False

        except Exception as e:
            print(f"      Error en alineaciones: {str(e)[:100]}")
            return False

    def _mapear_periodo(self, periodo_str: str) -> str:
        mapeo = {
            'ALL': 'ALL',
            '1ST': '1H',
            '2ND': '2H',
            'FIRST_HALF': '1H',
            'SECOND_HALF': '2H',
        }
        return mapeo.get(periodo_str, 'ALL')

    @sync_to_async
    def _limpiar_estadisticas(self, partido):
        EstadisticaPartido.objects.filter(partido=partido).delete()

    @sync_to_async
    def _crear_estadistica(self, partido, periodo, stats):
        EstadisticaPartido.objects.create(
            partido=partido,
            periodo=periodo,
            posesion_local=self._parse_float(stats.get('Ball possession', {}).get('home')),
            posesion_visitante=self._parse_float(stats.get('Ball possession', {}).get('away')),
            tiros_local=self._parse_int(stats.get('Total shots', {}).get('home')),
            tiros_visitante=self._parse_int(stats.get('Total shots', {}).get('away')),
            tiros_puerta_local=self._parse_int(stats.get('Shots on target', {}).get('home')),
            tiros_puerta_visitante=self._parse_int(stats.get('Shots on target', {}).get('away')),
            tiros_fuera_local=self._parse_int(stats.get('Shots off target', {}).get('home')),
            tiros_fuera_visitante=self._parse_int(stats.get('Shots off target', {}).get('away')),
            tiros_bloqueados_local=self._parse_int(stats.get('Blocked shots', {}).get('home')),
            tiros_bloqueados_visitante=self._parse_int(stats.get('Blocked shots', {}).get('away')),
            corners_local=self._parse_int(stats.get('Corner kicks', {}).get('home')),
            corners_visitante=self._parse_int(stats.get('Corner kicks', {}).get('away')),
            faltas_local=self._parse_int(stats.get('Fouls', {}).get('home')),
            faltas_visitante=self._parse_int(stats.get('Fouls', {}).get('away')),
            tarjetas_amarillas_local=self._parse_int(stats.get('Yellow cards', {}).get('home')),
            tarjetas_amarillas_visitante=self._parse_int(stats.get('Yellow cards', {}).get('away')),
            tarjetas_rojas_local=self._parse_int(stats.get('Red cards', {}).get('home')),
            tarjetas_rojas_visitante=self._parse_int(stats.get('Red cards', {}).get('away')),
            fueras_juego_local=self._parse_int(stats.get('Offsides', {}).get('home')),
            fueras_juego_visitante=self._parse_int(stats.get('Offsides', {}).get('away')),
            saques_banda_local=self._parse_int(stats.get('Throw-ins', {}).get('home')),
            saques_banda_visitante=self._parse_int(stats.get('Throw-ins', {}).get('away')),
            saques_puerta_local=self._parse_int(stats.get('Goal kicks', {}).get('home')),
            saques_puerta_visitante=self._parse_int(stats.get('Goal kicks', {}).get('away')),
        )

    @sync_to_async
    def _crear_eventos(self, partido, incidents):
        from futbol.models import Jugador

        EventoPartido.objects.filter(partido=partido).delete()

        tipo_map = {
            'goal': 'goal',
            'yellowCard': 'yellow_card',
            'redCard': 'red_card',
            'yellowRedCard': 'yellow_red_card',
            'substitution': 'substitution',
            'penalty': 'penalty',
            'penaltyMissed': 'penalty_missed',
            'ownGoal': 'own_goal',
            'varDecision': 'var',
            'injuryTime': 'injury',
            'period': 'period',
        }

        eventos_crear = []

        for incidente in incidents:
            tipo_sofascore = incidente.get('incidentType', '')
            tipo = tipo_map.get(tipo_sofascore, 'goal')

            jugador = None
            jugador_relacionado = None

            if incidente.get('player'):
                try:
                    jugador = Jugador.objects.get(sofascore_id=incidente['player']['id'])
                except Jugador.DoesNotExist:
                    pass

            if incidente.get('assist1'):
                try:
                    jugador_relacionado = Jugador.objects.get(sofascore_id=incidente['assist1']['id'])
                except Jugador.DoesNotExist:
                    pass

            evento = EventoPartido(
                sofascore_id=incidente.get('id'),
                partido=partido,
                jugador=jugador,
                jugador_relacionado=jugador_relacionado,
                minuto=incidente.get('time', 0),
                minuto_adicional=incidente.get('addedTime'),
                segundo=incidente.get('second'),
                tipo=tipo,
                texto_incidente=incidente.get('text', ''),
                es_local=incidente.get('isHome', True),
                datos_adicionales=incidente
            )
            eventos_crear.append(evento)

        if eventos_crear:
            EventoPartido.objects.bulk_create(eventos_crear, ignore_conflicts=True)

    @sync_to_async
    def _limpiar_alineaciones(self, partido):
        Alineacion.objects.filter(partido=partido).delete()

    @sync_to_async
    def _sync_alineacion_equipo(self, data, partido, equipo, es_local):
        from futbol.models import Jugador

        alineaciones_crear = []

        for player_data in data.get('players', []):
            player_info = player_data.get('player', {})
            try:
                jugador = Jugador.objects.get(sofascore_id=player_info['id'])

                stats = player_data.get('statistics', {})

                alineacion = Alineacion(
                    partido=partido,
                    jugador=jugador,
                    es_local=es_local,
                    es_titular=player_data.get('substitute', False) == False,
                    posicion=player_info.get('position', ''),
                    numero_camiseta=player_info.get('shirtNumber'),
                    rating=stats.get('rating'),
                    minutos_jugados=stats.get('minutesPlayed', 0),
                    goles=stats.get('goals', 0),
                    asistencias=stats.get('assists', 0),
                    tarjetas_amarillas=stats.get('yellowCards', 0),
                    tarjetas_rojas=stats.get('redCards', 0),
                    estadisticas_detalladas=stats
                )
                alineaciones_crear.append(alineacion)

            except Jugador.DoesNotExist:
                continue

        if alineaciones_crear:
            Alineacion.objects.bulk_create(alineaciones_crear, ignore_conflicts=True)

        return len(alineaciones_crear)

    @sync_to_async
    def _actualizar_flag_estadisticas(self, partido, valor):
        partido.tiene_estadisticas = valor
        partido.save(update_fields=['tiene_estadisticas'])

    @sync_to_async
    def _actualizar_flag_eventos(self, partido, valor):
        partido.tiene_incidentes = valor
        partido.save(update_fields=['tiene_incidentes'])

    @sync_to_async
    def _actualizar_flag_alineaciones(self, partido, valor):
        partido.tiene_lineups = valor
        partido.save(update_fields=['tiene_lineups'])


async def sync_estadisticas_todos_partidos(filtro='finished', liga_id=None, limite=None):
    """Sincronizar estadísticas de todos los partidos"""
    syncer = EstadisticasSyncer()

    try:
        # Obtener partidos
        partidos_query = Partido.objects.filter(estado=filtro).select_related(
            'equipo_local', 'equipo_visitante', 'liga'
        ).order_by('-fecha_hora')

        if liga_id:
            partidos_query = partidos_query.filter(liga_id=liga_id)

        if limite:
            partidos_query = partidos_query[:limite]

        partidos = await sync_to_async(list)(partidos_query)

        total = len(partidos)

        print(f"\nSincronizando estadísticas de {total} partidos...")
        print("=" * 70)

        for i, partido in enumerate(partidos, 1):
            syncer.stats['procesados'] += 1

            print(f"\n[{i}/{total}] {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}")
            print(f"    ID: {partido.sofascore_id} | Fecha: {partido.fecha_hora.strftime('%Y-%m-%d')}")

            try:
                # Estadísticas
                tiene_stats = await syncer.sync_estadisticas_partido(partido)
                status_stats = "OK" if tiene_stats else "NO"
                print(f"    Estadísticas: {status_stats}")

                # Eventos
                tiene_eventos = await syncer.sync_eventos_partido(partido)
                status_eventos = "OK" if tiene_eventos else "NO"
                print(f"    Eventos: {status_eventos}")

                # Alineaciones
                tiene_lineups = await syncer.sync_alineaciones_partido(partido)
                status_lineups = "OK" if tiene_lineups else "NO"
                print(f"    Alineaciones: {status_lineups}")

            except Exception as e:
                syncer.stats['errores'] += 1
                print(f"    ERROR: {str(e)[:100]}")

            # Pausa cada 10 partidos
            if i % 10 == 0:
                print(f"\n    Pausa... ({i}/{total} procesados)")
                await asyncio.sleep(2)

        # Resumen
        print("\n" + "=" * 70)
        print("RESUMEN DE SINCRONIZACIÓN")
        print("=" * 70)
        print(f"Partidos procesados: {syncer.stats['procesados']}")
        print(f"Con estadísticas: {syncer.stats['con_estadisticas']}")
        print(f"Con eventos: {syncer.stats['con_eventos']}")
        print(f"Con alineaciones: {syncer.stats['con_alineaciones']}")
        print(f"Errores: {syncer.stats['errores']}")
        print("=" * 70)

    finally:
        await syncer.close()


async def sync_partido_individual(event_id: int):
    """Sincronizar estadísticas de un partido específico"""
    syncer = EstadisticasSyncer()

    try:
        partido = await sync_to_async(Partido.objects.get)(sofascore_id=event_id)

        print(f"\nSincronizando partido: {partido}")
        print("=" * 70)

        # Estadísticas
        print("\n1. Sincronizando estadísticas...")
        tiene_stats = await syncer.sync_estadisticas_partido(partido)
        print(f"   Resultado: {'OK' if tiene_stats else 'NO DISPONIBLE'}")

        # Eventos
        print("\n2. Sincronizando eventos...")
        tiene_eventos = await syncer.sync_eventos_partido(partido)
        print(f"   Resultado: {'OK' if tiene_eventos else 'NO DISPONIBLE'}")

        # Alineaciones
        print("\n3. Sincronizando alineaciones...")
        tiene_lineups = await syncer.sync_alineaciones_partido(partido)
        print(f"   Resultado: {'OK' if tiene_lineups else 'NO DISPONIBLE'}")

        # Verificar en BD
        print("\n4. Verificando en base de datos...")
        stats_count = await sync_to_async(EstadisticaPartido.objects.filter(partido=partido).count)()
        eventos_count = await sync_to_async(EventoPartido.objects.filter(partido=partido).count)()
        alineaciones_count = await sync_to_async(Alineacion.objects.filter(partido=partido).count)()

        print(f"   Estadísticas guardadas: {stats_count}")
        print(f"   Eventos guardados: {eventos_count}")
        print(f"   Alineaciones guardadas: {alineaciones_count}")

    except Partido.DoesNotExist:
        print(f"\nERROR: Partido con ID {event_id} no existe en la base de datos")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await syncer.close()


async def sync_estadisticas_top5_ligas(limite_por_liga=None):
    """Sincronizar estadísticas SOLO de las Top 5 ligas"""
    syncer = EstadisticasSyncer()

    # IDs de las Top 5 ligas
    TOP_5_IDS = [8, 17, 23, 35, 34]  # La Liga, Premier, Serie A, Bundesliga, Ligue 1

    try:
        # Obtener ligas Top 5
        ligas_query = Liga.objects.filter(sofascore_id__in=TOP_5_IDS)
        ligas = await sync_to_async(list)(ligas_query)

        print(f"\nSincronizando estadísticas de {len(ligas)} ligas principales")
        print("=" * 70)

        total_procesados = 0

        for liga in ligas:
            print(f"\n{'=' * 70}")
            print(f"🏆 {liga.nombre}")
            print(f"{'=' * 70}")

            # Obtener partidos finalizados de esta liga
            partidos_query = Partido.objects.filter(
                liga=liga,
                estado='finished'
            ).select_related('equipo_local', 'equipo_visitante').order_by('-fecha_hora')

            if limite_por_liga:
                partidos_query = partidos_query[:limite_por_liga]

            partidos = await sync_to_async(list)(partidos_query)

            print(f"\nPartidos a procesar: {len(partidos)}")

            for i, partido in enumerate(partidos, 1):
                syncer.stats['procesados'] += 1
                total_procesados += 1

                print(f"[{i}/{len(partidos)}] {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}",
                      end=' ')

                try:
                    tiene_stats = await syncer.sync_estadisticas_partido(partido)
                    tiene_eventos = await syncer.sync_eventos_partido(partido)
                    tiene_lineups = await syncer.sync_alineaciones_partido(partido)

                    status = []
                    if tiene_stats: status.append("Stats")
                    if tiene_eventos: status.append("Eventos")
                    if tiene_lineups: status.append("Lineups")

                    print(f"✓ {', '.join(status) if status else 'Sin datos'}")

                except Exception as e:
                    syncer.stats['errores'] += 1
                    print(f"✗ Error")

                if i % 10 == 0:
                    await asyncio.sleep(2)

            print(f"\n✓ {liga.nombre} completada")

        # Resumen
        print("\n" + "=" * 70)
        print("RESUMEN FINAL")
        print("=" * 70)
        print(f"Partidos procesados: {syncer.stats['procesados']}")
        print(f"Con estadísticas: {syncer.stats['con_estadisticas']}")
        print(f"Con eventos: {syncer.stats['con_eventos']}")
        print(f"Con alineaciones: {syncer.stats['con_alineaciones']}")
        print(f"Errores: {syncer.stats['errores']}")
        print("=" * 70)

    finally:
        await syncer.close()


async def main():
    print("\n" + "=" * 70)
    print("SINCRONIZACIÓN DE ESTADÍSTICAS - TOP 5 LIGAS")
    print("=" * 70)
    print("\nOpciones:")
    print("1. Sincronizar TODAS las estadísticas de Top 5 ligas")
    print("2. Sincronizar últimos N partidos por liga")
    print("3. Sincronizar una liga específica (todas sus temporadas)")
    print("4. Sincronizar partido específico (por ID)")
    print("5. Salir")

    opcion = input("\nSelecciona opción (1-5): ").strip()

    if opcion == '1':
        confirmar = input("Esto puede tardar bastante. Continuar? (s/n): ")
        if confirmar.lower() == 's':
            await sync_estadisticas_top5_ligas()

    elif opcion == '2':
        limite = input("Cuántos partidos por liga? (ej: 50): ").strip()
        if limite.isdigit():
            await sync_estadisticas_top5_ligas(limite_por_liga=int(limite))
        else:
            print("Número inválido")

    elif opcion == '3':
        # Mostrar ligas disponibles
        TOP_5_IDS = [8, 17, 23, 35, 34]
        ligas = await sync_to_async(list)(Liga.objects.filter(sofascore_id__in=TOP_5_IDS))

        if not ligas:
            print("No hay ligas Top 5 en la base de datos")
            return

        print("\nLigas disponibles:")
        for i, liga in enumerate(ligas, 1):
            print(f"{i}. {liga.nombre}")

        seleccion = input(f"\nSelecciona (1-{len(ligas)}): ").strip()
        if seleccion.isdigit() and 1 <= int(seleccion) <= len(ligas):
            liga_seleccionada = ligas[int(seleccion) - 1]
            await sync_estadisticas_todos_partidos(liga_id=liga_seleccionada.id)
        else:
            print("Selección inválida")

    elif opcion == '4':
        event_id = input("ID del partido en Sofascore: ").strip()
        if event_id.isdigit():
            await sync_partido_individual(int(event_id))
        else:
            print("ID inválido")

    elif opcion == '5':
        print("\nHasta luego!")
        return

    else:
        print("Opción inválida")


if __name__ == "__main__":
    asyncio.run(main())