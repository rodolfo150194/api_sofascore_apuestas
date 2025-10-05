"""
Script para sincronizar datos de Sofascore con los modelos de Django
Uso: python sync_sofascore.py [opciones]
"""

import asyncio
import os
import django
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sofascore_project.settings')  # Cambiar por tu proyecto
django.setup()


from futbol.models import *
from futbol.sofascore_api import SofascoreAPI

"""
seasons = https://api.sofascore.com/api/v1/unique-tournament/8/seasons/
torneo = https://api.sofascore.com/api/v1/tournament/8/
"""
class SofascoreSyncManager:
    """Gestor principal para sincronizar datos de Sofascore"""

    def __init__(self):
        self.api = SofascoreAPI()
        self.stats = {
            'paises': 0,
            'ligas': 0,
            'temporadas': 0,
            'equipos': 0,
            'jugadores': 0,
            'partidos': 0,
            'estadisticas': 0,
            'eventos': 0,
            'alineaciones': 0
        }

    async def close(self):
        """Cerrar la conexión de la API"""
        await self.api.close()

    # ============================================
    # MÉTODOS PARA SINCRONIZAR PAÍSES Y LIGAS
    # ============================================

    @sync_to_async
    def sync_pais(self, pais_data: Dict) -> Pais:
        """Sincronizar un país"""
        pais, created = Pais.objects.get_or_create(
            nombre=pais_data.get('name', ''),
            defaults={
                'codigo': pais_data.get('alpha2', ''),
                'bandera_url': pais_data.get('flag', '')
            }
        )
        if created:
            self.stats['paises'] += 1
            print(f"✓ País creado: {pais.nombre}")
        return pais

    @sync_to_async
    def sync_liga(self, liga_data: Dict, pais: Optional[Pais] = None) -> Liga:
        """Sincronizar una liga/torneo"""
        sofascore_id = liga_data.get('id')

        liga, created = Liga.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults={
                'nombre': liga_data.get('name', ''),
                'pais': pais,
                'logo_url': f"https://www.sofascore.com/static/images/unique-tournament/{sofascore_id}.png",
                'tipo': self._determinar_tipo_liga(liga_data.get('name', ''))
            }
        )

        if created:
            self.stats['ligas'] += 1
            print(f"✓ Liga creada: {liga.nombre}")

        return liga

    def _determinar_tipo_liga(self, nombre: str) -> str:
        """Determinar el tipo de liga basado en el nombre"""
        nombre_lower = nombre.lower()
        if 'cup' in nombre_lower or 'copa' in nombre_lower:
            return 'copa'
        elif 'champions' in nombre_lower or 'europa' in nombre_lower or 'libertadores' in nombre_lower:
            return 'internacional'
        return 'liga'

    @sync_to_async
    def sync_temporada(self, temporada_data: Dict, liga: Liga) -> Temporada:
        """Sincronizar una temporada"""
        sofascore_id = temporada_data.get('id')
        nombre = temporada_data.get('name', temporada_data.get('year', ''))

        # Extraer años del nombre
        annos = nombre.split('/')
        anno_inicio = int(annos[0]) if annos else datetime.now().year
        anno_fin = int(annos[1]) if len(annos) > 1 else None

        temporada, created = Temporada.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults={
                'liga': liga,
                'nombre': nombre,
                'año_inicio': anno_inicio,
                'año_fin': anno_fin,
                'activa': True
            }
        )

        if created:
            self.stats['temporadas'] += 1
            print(f"✓ Temporada creada: {temporada.nombre}")

        return temporada

    # ============================================
    # MÉTODOS PARA SINCRONIZAR EQUIPOS
    # ============================================

    @sync_to_async
    def sync_equipo(self, equipo_data: Dict) -> Equipo:
        """Sincronizar un equipo"""
        sofascore_id = equipo_data.get('id')

        # Obtener país si existe
        pais = None
        if equipo_data.get('country'):
            pais_obj = Pais.objects.filter(nombre=equipo_data['country'].get('name')).first()
            pais = pais_obj

        equipo, created = Equipo.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults={
                'nombre': equipo_data.get('name', ''),
                'nombre_corto': equipo_data.get('shortName', ''),
                'pais': pais,
                'logo_url': f"https://www.sofascore.com/static/images/team/{sofascore_id}.png",
            }
        )

        if created:
            self.stats['equipos'] += 1
            print(f"✓ Equipo creado: {equipo.nombre}")

        return equipo

    async def sync_equipo_completo(self, team_id: int) -> Equipo:
        """Sincronizar información completa de un equipo"""
        try:
            equipo_data = await self.api.get_equipo_info(team_id)
            equipo = await self.sync_equipo(equipo_data.get('team', {}))

            # Actualizar info adicional
            await self._actualizar_info_equipo(equipo, equipo_data.get('team', {}))
            await self.sync_jugadores_equipo(team_id, equipo)

            return equipo

        except Exception as e:
            print(f"✗ Error sincronizando equipo {team_id}: {e}")
            return None

    @sync_to_async
    def _actualizar_info_equipo(self, equipo, team_info):
        """Actualizar información adicional del equipo"""
        if team_info.get('venue'):
            equipo.estadio = team_info['venue'].get('stadium', {}).get('name', '')
        if team_info.get('teamColors'):
            equipo.colores = team_info['teamColors']
        equipo.save()

    # ============================================
    # MÉTODOS PARA SINCRONIZAR JUGADORES
    # ============================================

    async def sync_jugadores_equipo(self, team_id: int, equipo: Equipo):
        """Sincronizar jugadores de un equipo"""
        try:
            data = await self.api.get_equipo_jugadores(team_id)
            jugadores_data = data.get('players', [])

            for jugador_data in jugadores_data:
                await self.sync_jugador(jugador_data.get('player', {}), equipo)

            print(f"✓ Sincronizados {len(jugadores_data)} jugadores de {equipo.nombre}")

        except Exception as e:
            print(f"✗ Error sincronizando jugadores: {e}")

    @sync_to_async
    def sync_jugador(self, jugador_data: Dict, equipo: Equipo) -> Jugador:
        """Sincronizar un jugador"""
        sofascore_id = jugador_data.get('id')

        posicion_map = {'G': 'POR', 'D': 'DEF', 'M': 'MED', 'F': 'DEL'}
        posicion_sofascore = jugador_data.get('position', 'M')
        posicion = posicion_map.get(posicion_sofascore, 'MED')

        fecha_nacimiento = None
        if jugador_data.get('dateOfBirthTimestamp'):
            fecha_nacimiento = datetime.fromtimestamp(jugador_data['dateOfBirthTimestamp']).date()

        jugador, created = Jugador.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults={
                'nombre': jugador_data.get('name', ''),
                'nombre_completo': jugador_data.get('name', ''),
                'equipo': equipo,
                'fecha_nacimiento': fecha_nacimiento,
                'nacionalidad': jugador_data.get('country', {}).get('name', ''),
                'posicion': posicion,
                'altura': jugador_data.get('height'),
                'foto_url': f"https://www.sofascore.com/static/images/player/{sofascore_id}.png",
            }
        )

        if created:
            self.stats['jugadores'] += 1

        return jugador

    # ============================================
    # MÉTODOS PARA SINCRONIZAR PARTIDOS
    # ============================================

    async def sync_partidos_fecha(self, fecha: datetime, deporte: str = "football"):
        """Sincronizar partidos de una fecha"""
        try:
            data = await self.api.get_partidos_fecha(fecha, deporte)
            eventos = data.get('events', [])

            print(f"\n📅 Sincronizando {len(eventos)} partidos del {fecha.strftime('%Y-%m-%d')}...")

            for evento in eventos:
                await self.sync_partido(evento)

            print(f"✓ Completado: {len(eventos)} partidos sincronizados")

        except Exception as e:
            print(f"✗ Error sincronizando partidos de {fecha}: {e}")

    async def sync_partido(self, evento_data: Dict) -> Optional[Partido]:
        """Sincronizar un partido"""
        try:
            sofascore_id = evento_data.get('id')

            # Sincronizar datos relacionados
            torneo_data = evento_data.get('tournament', {})
            pais_data = torneo_data.get('category', {}).get('country')
            pais = await self.sync_pais(pais_data) if pais_data else None
            liga = await self.sync_liga(torneo_data, pais)

            season_data = evento_data.get('season', {})
            temporada = await self.sync_temporada(season_data, liga)

            equipo_local = await self.sync_equipo(evento_data.get('homeTeam', {}))
            equipo_visitante = await self.sync_equipo(evento_data.get('awayTeam', {}))

            # Mapear estado
            estado_map = {
                'notstarted': 'notstarted',
                'inprogress': 'inprogress',
                'finished': 'finished',
                'postponed': 'postponed',
                'cancelled': 'cancelled',
                'abandoned': 'abandoned'
            }
            estado = estado_map.get(
                evento_data.get('status', {}).get('type', 'notstarted'),
                'notstarted'
            )

            # Crear partido
            fecha_hora = datetime.fromtimestamp(evento_data.get('startTimestamp', 0))
            fecha_hora = timezone.make_aware(fecha_hora) if timezone.is_naive(fecha_hora) else fecha_hora

            partido = await self._crear_partido(
                sofascore_id, liga, temporada, equipo_local, equipo_visitante,
                fecha_hora, evento_data, estado
            )

            # Sincronizar detalles si está finalizado
            if estado in ['finished', 'inprogress']:
                await self.sync_detalles_partido(sofascore_id, partido)

            return partido

        except Exception as e:
            print(f"  ✗ Error sincronizando partido {evento_data.get('id')}: {e}")
            return None

    @sync_to_async
    def _crear_partido(self, sofascore_id, liga, temporada, equipo_local,
                       equipo_visitante, fecha_hora, evento_data, estado):
        """Crear o actualizar partido en la BD"""
        partido, created = Partido.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults={
                'liga': liga,
                'temporada': temporada,
                'equipo_local': equipo_local,
                'equipo_visitante': equipo_visitante,
                'fecha_hora': fecha_hora,
                'goles_local': evento_data.get('homeScore', {}).get('current'),
                'goles_visitante': evento_data.get('awayScore', {}).get('current'),
                'estado': estado,
            }
        )

        if created:
            self.stats['partidos'] += 1
            print(f"  ✓ Partido: {equipo_local.nombre} vs {equipo_visitante.nombre}")

        return partido

    async def sync_detalles_partido(self, event_id: int, partido: Partido):
        """Sincronizar detalles del partido"""
        try:
            await self.sync_estadisticas_partido(event_id, partido)
            await self.sync_eventos_partido(event_id, partido)
            await self.sync_alineaciones_partido(event_id, partido)
        except Exception as e:
            print(f"  ⚠ Error en detalles: {e}")

    async def sync_estadisticas_partido(self, event_id: int, partido: Partido):
        """Sincronizar estadísticas"""
        try:
            data = await self.api.get_partido_estadisticas(event_id)

            for grupo in data.get('statistics', []):
                periodo = 'ALL'
                if grupo.get('period') == '1ST':
                    periodo = '1H'
                elif grupo.get('period') == '2ND':
                    periodo = '2H'

                stats = {}
                for stat in grupo.get('groups', [{}])[0].get('statisticsItems', []):
                    nombre = stat.get('name')
                    stats[nombre] = {
                        'home': stat.get('home'),
                        'away': stat.get('away')
                    }

                await self._crear_estadistica(partido, periodo, stats)

            self.stats['estadisticas'] += 1

        except Exception as e:
            print(f"    ⚠ Error en estadísticas: {e}")

    @sync_to_async
    def _crear_estadistica(self, partido, periodo, stats):
        """Crear estadística en BD"""
        EstadisticaPartido.objects.update_or_create(
            partido=partido,
            periodo=periodo,
            defaults={
                'posesion_local': self._parse_float(stats.get('Ball possession', {}).get('home')),
                'posesion_visitante': self._parse_float(stats.get('Ball possession', {}).get('away')),
                'tiros_local': self._parse_int(stats.get('Total shots', {}).get('home')),
                'tiros_visitante': self._parse_int(stats.get('Total shots', {}).get('away')),
                'tiros_puerta_local': self._parse_int(stats.get('Shots on target', {}).get('home')),
                'tiros_puerta_visitante': self._parse_int(stats.get('Shots on target', {}).get('away')),
                'corners_local': self._parse_int(stats.get('Corner kicks', {}).get('home')),
                'corners_visitante': self._parse_int(stats.get('Corner kicks', {}).get('away')),
                'faltas_local': self._parse_int(stats.get('Fouls', {}).get('home')),
                'faltas_visitante': self._parse_int(stats.get('Fouls', {}).get('away')),
                'tarjetas_amarillas_local': self._parse_int(stats.get('Yellow cards', {}).get('home')),
                'tarjetas_amarillas_visitante': self._parse_int(stats.get('Yellow cards', {}).get('away')),
                'tarjetas_rojas_local': self._parse_int(stats.get('Red cards', {}).get('home')),
                'tarjetas_rojas_visitante': self._parse_int(stats.get('Red cards', {}).get('away')),
            }
        )

    async def sync_eventos_partido(self, event_id: int, partido: Partido):
        """Sincronizar eventos del partido"""
        try:
            data = await self.api.get_partido_incidentes(event_id)
            await self._crear_eventos(partido, data.get('incidents', []))
            self.stats['eventos'] += len(data.get('incidents', []))
        except Exception as e:
            print(f"    ⚠ Error en eventos: {e}")

    @sync_to_async
    def _crear_eventos(self, partido, incidents):
        """Crear eventos en BD"""
        EventoPartido.objects.filter(partido=partido).delete()

        tipo_map = {
            'goal': 'goal',
            'yellowCard': 'yellow_card',
            'redCard': 'red_card',
            'substitution': 'substitution',
            'penalty': 'penalty',
            'ownGoal': 'own_goal',
            'varDecision': 'var'
        }

        for incidente in incidents:
            tipo = tipo_map.get(incidente.get('incidentType'), 'goal')

            jugador = None
            if incidente.get('player'):
                try:
                    jugador = Jugador.objects.get(sofascore_id=incidente['player']['id'])
                except Jugador.DoesNotExist:
                    pass

            EventoPartido.objects.create(
                partido=partido,
                jugador=jugador,
                minuto=incidente.get('time', 0),
                tipo=tipo,
                es_local=incidente.get('isHome', True)
            )

    async def sync_alineaciones_partido(self, event_id: int, partido: Partido):
        """Sincronizar alineaciones"""
        try:
            data = await self.api.get_partido_lineups(event_id)
            await self._limpiar_alineaciones(partido)

            if data.get('home'):
                await self._sync_alineacion_equipo(
                    data['home'], partido, partido.equipo_local, True
                )

            if data.get('away'):
                await self._sync_alineacion_equipo(
                    data['away'], partido, partido.equipo_visitante, False
                )

        except Exception as e:
            print(f"    ⚠ Error en alineaciones: {e}")

    @sync_to_async
    def _limpiar_alineaciones(self, partido):
        """Limpiar alineaciones anteriores"""
        Alineacion.objects.filter(partido=partido).delete()

    @sync_to_async
    def _sync_alineacion_equipo(self, data: Dict, partido: Partido, equipo: Equipo, es_local: bool):
        """Sincronizar alineación de un equipo"""
        for player_data in data.get('players', []):
            player_info = player_data.get('player', {})
            try:
                jugador = Jugador.objects.get(sofascore_id=player_info['id'])

                Alineacion.objects.create(
                    partido=partido,
                    jugador=jugador,
                    es_local=es_local,
                    es_titular=True,
                    posicion=player_info.get('position', ''),
                    numero_camiseta=player_info.get('shirtNumber'),
                    rating=player_data.get('statistics', {}).get('rating')
                )
                self.stats['alineaciones'] += 1

            except Jugador.DoesNotExist:
                pass

    # ============================================
    # MÉTODOS DE SINCRONIZACIÓN MASIVA
    # ============================================

    async def sync_liga_completa(self, tournament_id: int, season_id: int):
        """Sincronizar liga completa"""
        try:
            print(f"\n🏆 Sincronizando liga {tournament_id}, temporada {season_id}...")

            torneo_data = await self.api.get_torneo_info(tournament_id)
            liga = await self.sync_liga(torneo_data.get('uniqueTournament', {}))
            temporada = await self.sync_temporada(torneo_data.get('season', {}), liga)

            partidos_data = await self.api.get_torneo_partidos(tournament_id, season_id)
            eventos = partidos_data.get('events', [])

            print(f"📊 Encontrados {len(eventos)} partidos")

            for i, evento in enumerate(eventos, 1):
                print(f"  [{i}/{len(eventos)}] ", end='')
                await self.sync_partido(evento)

                if i % 10 == 0:
                    await asyncio.sleep(1)

            print(f"✅ Liga sincronizada: {liga.nombre}")

        except Exception as e:
            print(f"✗ Error sincronizando liga: {e}")
            import traceback
            traceback.print_exc()

    async def sync_partidos_rango_fechas(self, fecha_inicio: datetime, fecha_fin: datetime):
        """Sincronizar rango de fechas"""
        fecha_actual = fecha_inicio

        while fecha_actual <= fecha_fin:
            await self.sync_partidos_fecha(fecha_actual)
            fecha_actual += timedelta(days=1)
            await asyncio.sleep(1)

    # ============================================
    # MÉTODOS AUXILIARES
    # ============================================

    def _parse_int(self, value) -> int:
        """Convertir a int"""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value) -> Optional[float]:
        """Convertir a float"""
        try:
            if isinstance(value, str):
                value = value.rstrip('%')
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def print_stats(self):
        """Imprimir estadísticas"""
        print("\n" + "=" * 50)
        print("📊 ESTADÍSTICAS DE SINCRONIZACIÓN")
        print("=" * 50)
        for key, value in self.stats.items():
            if value > 0:
                print(f"  {key.capitalize()}: {value}")
        print("=" * 50)


# ============================================
# FUNCIONES PRINCIPALES
# ============================================

async def sync_partidos_hoy():
    """Sincronizar partidos de hoy"""
    manager = SofascoreSyncManager()
    try:
        await manager.sync_partidos_fecha(datetime.now())
        manager.print_stats()
    finally:
        await manager.close()


async def sync_liga_espanola():
    """Sincronizar La Liga"""
    manager = SofascoreSyncManager()
    try:
        await manager.sync_liga_completa(8, 61643)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_premier_league():
    """Sincronizar Premier League"""
    manager = SofascoreSyncManager()
    try:
        await manager.sync_liga_completa(17, 61627)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_champions_league():
    """Sincronizar Champions League"""
    manager = SofascoreSyncManager()
    try:
        await manager.sync_liga_completa(7, 52162)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_ultima_semana():
    """Sincronizar última semana"""
    manager = SofascoreSyncManager()
    try:
        hoy = datetime.now()
        hace_semana = hoy - timedelta(days=7)
        await manager.sync_partidos_rango_fechas(hace_semana, hoy)
        manager.print_stats()
    finally:
        await manager.close()


# ============================================
# MENÚ PRINCIPAL
# ============================================

async def main():
    """Menú principal"""
    print("\n" + "=" * 50)
    print("⚽ SINCRONIZADOR DE SOFASCORE")
    print("=" * 50)
    print("\nOpciones disponibles:")
    print("1. Sincronizar partidos de hoy")
    print("2. Sincronizar La Liga Española completa")
    print("3. Sincronizar Premier League completa")
    print("4. Sincronizar Champions League")
    print("5. Sincronizar última semana")
    print("6. Salir")

    opcion = input("\nSelecciona una opción (1-6): ").strip()

    if opcion == '1':
        await sync_partidos_hoy()
    elif opcion == '2':
        await sync_liga_espanola()
    elif opcion == '3':
        await sync_premier_league()
    elif opcion == '4':
        await sync_champions_league()
    elif opcion == '5':
        await sync_ultima_semana()
    elif opcion == '6':
        print("\n¡Hasta luego! 👋")
        return
    else:
        print("\n❌ Opción no válida")


if __name__ == "__main__":
    asyncio.run(main())