"""
Script mejorado para sincronizar datos de Sofascore con Django
Uso: python poblar_bd_sofascore.py
"""

import asyncio
import os
import django
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sofascore_project.settings')
django.setup()

from futbol.models import *
from futbol.sofascore_api import SofascoreAPI

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SofascoreSyncManager:
    """Gestor mejorado para sincronizar datos de Sofascore"""

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
        self.errores = []

    async def close(self):
        """Cerrar la conexión de la API"""
        await self.api.close()

    # ============================================
    # MÉTODOS PARA SINCRONIZAR PAÍSES Y LIGAS
    # ============================================

    @sync_to_async
    def sync_pais(self, pais_data: Dict) -> Optional[Pais]:
        """Sincronizar un país"""
        if not pais_data or not pais_data.get('name'):
            return None

        pais, created = Pais.objects.get_or_create(
            nombre=pais_data.get('name', ''),
            defaults={
                'sofascore_id': pais_data.get('id'),
                'codigo': pais_data.get('alpha2', ''),
                'alpha2': pais_data.get('alpha2', ''),
                'alpha3': pais_data.get('alpha3', ''),
                'bandera_url': pais_data.get('flag', '')
            }
        )
        if created:
            self.stats['paises'] += 1
            logger.info(f"✓ País creado: {pais.nombre}")
        return pais

    @sync_to_async
    def sync_liga(self, liga_data: Dict, pais: Optional[Pais] = None) -> Optional[Liga]:
        """Sincronizar una liga/torneo"""
        if not liga_data or not liga_data.get('id'):
            return None

        sofascore_id = liga_data.get('id')

        defaults = {
            'nombre': liga_data.get('name', ''),
            'nombre_corto': liga_data.get('shortName', ''),
            'slug': liga_data.get('slug', ''),
            'pais': pais,
            'logo_url': f"https://www.sofascore.com/static/images/unique-tournament/{sofascore_id}.png",
            'tipo': self._determinar_tipo_liga(liga_data.get('name', '')),
            'tiene_tabla_posiciones': liga_data.get('hasStandingsGroups', True),
            'tiene_playoff': liga_data.get('hasPlayoffSeries', False),
        }

        liga, created = Liga.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults=defaults
        )

        if created:
            self.stats['ligas'] += 1
            logger.info(f"✓ Liga creada: {liga.nombre}")

        return liga

    def _determinar_tipo_liga(self, nombre: str) -> str:
        """Determinar el tipo de liga basado en el nombre"""
        nombre_lower = nombre.lower()
        if 'cup' in nombre_lower or 'copa' in nombre_lower or 'pokal' in nombre_lower:
            return 'copa'
        elif any(x in nombre_lower for x in ['champions', 'europa', 'libertadores', 'sudamericana', 'conference']):
            return 'internacional'
        elif 'friendly' in nombre_lower or 'amistoso' in nombre_lower:
            return 'amistoso'
        return 'liga'

    @sync_to_async
    def sync_temporada(self, temporada_data: Dict, liga: Liga) -> Optional[Temporada]:
        """Sincronizar una temporada"""
        if not temporada_data or not temporada_data.get('id'):
            return None

        sofascore_id = temporada_data.get('id')
        nombre = temporada_data.get('name', temporada_data.get('year', ''))

        # Extraer años del nombre
        try:
            if '/' in nombre:
                annos = nombre.split('/')
                anno_inicio = int(annos[0])
                anno_fin = int('20' + annos[1]) if len(annos[1]) == 2 else int(annos[1])
            else:
                anno_inicio = int(nombre)
                anno_fin = anno_inicio
        except (ValueError, IndexError):
            anno_inicio = datetime.now().year
            anno_fin = None

        # Primero intentar buscar por sofascore_id
        try:
            temporada = Temporada.objects.get(sofascore_id=sofascore_id)
            # Actualizar si es necesario
            temporada.liga = liga
            temporada.nombre = nombre
            temporada.year = temporada_data.get('year', '')
            temporada.año_inicio = anno_inicio
            temporada.año_fin = anno_fin
            temporada.save()
            return temporada
        except Temporada.DoesNotExist:
            pass

        # Si no existe por sofascore_id, buscar por liga y año
        try:
            temporada = Temporada.objects.get(liga=liga, año_inicio=anno_inicio)
            # Actualizar el sofascore_id
            temporada.sofascore_id = sofascore_id
            temporada.nombre = nombre
            temporada.year = temporada_data.get('year', '')
            temporada.año_fin = anno_fin
            temporada.save()
            return temporada
        except Temporada.DoesNotExist:
            pass

        # Crear nueva temporada
        temporada = Temporada.objects.create(
            sofascore_id=sofascore_id,
            liga=liga,
            nombre=nombre,
            year=temporada_data.get('year', ''),
            año_inicio=anno_inicio,
            año_fin=anno_fin,
            activa=True
        )

        self.stats['temporadas'] += 1
        logger.info(f"✓ Temporada creada: {temporada.nombre}")

        return temporada

    # ============================================
    # MÉTODOS PARA SINCRONIZAR EQUIPOS
    # ============================================

    @sync_to_async
    def sync_equipo(self, equipo_data: Dict) -> Optional[Equipo]:
        """Sincronizar un equipo"""
        if not equipo_data or not equipo_data.get('id'):
            return None

        sofascore_id = equipo_data.get('id')

        # Obtener país si existe
        pais = None
        if equipo_data.get('country'):
            try:
                pais = Pais.objects.get(nombre=equipo_data['country'].get('name'))
            except Pais.DoesNotExist:
                pass

        defaults = {
            'nombre': equipo_data.get('name', ''),
            'nombre_corto': equipo_data.get('shortName', ''),
            'slug': equipo_data.get('slug', ''),
            'pais': pais,
            'logo_url': f"https://www.sofascore.com/static/images/team/{sofascore_id}.png",
            'tipo': equipo_data.get('type', 'club'),
        }

        # Información adicional si está disponible
        if equipo_data.get('teamColors'):
            defaults['colores'] = equipo_data['teamColors']
        if equipo_data.get('manager'):
            defaults['manager'] = equipo_data['manager'].get('name', '')

        equipo, created = Equipo.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults=defaults
        )

        if created:
            self.stats['equipos'] += 1
            logger.info(f"✓ Equipo creado: {equipo.nombre}")

        return equipo

    async def sync_equipo_completo(self, team_id: int) -> Optional[Equipo]:
        """Sincronizar información completa de un equipo"""
        try:
            equipo_data = await self.api.get_equipo_info(team_id)
            team_info = equipo_data.get('team', {})
            equipo = await self.sync_equipo(team_info)

            if equipo:
                # Actualizar info adicional
                await self._actualizar_info_equipo(equipo, team_info)
                await self.sync_jugadores_equipo(team_id, equipo)

            return equipo

        except Exception as e:
            logger.error(f"✗ Error sincronizando equipo {team_id}: {e}")
            self.errores.append(f"Equipo {team_id}: {e}")
            return None

    @sync_to_async
    def _actualizar_info_equipo(self, equipo: Equipo, team_info: Dict):
        """Actualizar información adicional del equipo"""
        actualizado = False

        if team_info.get('venue'):
            venue = team_info['venue']
            if venue.get('stadium', {}).get('name'):
                equipo.estadio = venue['stadium']['name']
                actualizado = True
            if venue.get('stadium', {}).get('capacity'):
                equipo.capacidad_estadio = venue['stadium']['capacity']
                actualizado = True

        if team_info.get('teamColors'):
            equipo.colores = team_info['teamColors']
            actualizado = True

        if team_info.get('foundationDateTimestamp'):
            try:
                fecha_fundacion = datetime.fromtimestamp(team_info['foundationDateTimestamp'])
                equipo.fundacion = fecha_fundacion.year
                actualizado = True
            except:
                pass

        if actualizado:
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

            logger.info(f"✓ Sincronizados {len(jugadores_data)} jugadores de {equipo.nombre}")

        except Exception as e:
            logger.warning(f"⚠ Error sincronizando jugadores de {equipo.nombre}: {e}")

    @sync_to_async
    def sync_jugador(self, jugador_data: Dict, equipo: Equipo) -> Optional[Jugador]:
        """Sincronizar un jugador"""
        if not jugador_data or not jugador_data.get('id'):
            return None

        sofascore_id = jugador_data.get('id')

        # Mapeo de posiciones
        posicion_map = {'G': 'POR', 'D': 'DEF', 'M': 'MED', 'F': 'DEL'}
        posicion_sofascore = jugador_data.get('position', 'M')
        posicion = posicion_map.get(posicion_sofascore, 'MED')

        # Fecha de nacimiento
        fecha_nacimiento = None
        fecha_nacimiento_timestamp = jugador_data.get('dateOfBirthTimestamp')
        if fecha_nacimiento_timestamp:
            try:
                fecha_nacimiento = datetime.fromtimestamp(fecha_nacimiento_timestamp).date()
            except:
                pass

        # País de nacionalidad
        nacionalidad = None
        if jugador_data.get('country'):
            try:
                nacionalidad = Pais.objects.get(nombre=jugador_data['country'].get('name'))
            except Pais.DoesNotExist:
                pass

        defaults = {
            'nombre': jugador_data.get('name', ''),
            'nombre_completo': jugador_data.get('name', ''),
            'slug': jugador_data.get('slug', ''),
            'equipo': equipo,
            'fecha_nacimiento': fecha_nacimiento,
            'fecha_nacimiento_timestamp': fecha_nacimiento_timestamp,
            'nacionalidad': nacionalidad,
            'posicion': posicion,
            'posicion_detallada': jugador_data.get('positionDescription', ''),
            'altura': jugador_data.get('height'),
            'peso': jugador_data.get('weight'),
            'numero_camiseta': jugador_data.get('jerseyNumber'),
            'foto_url': f"https://www.sofascore.com/static/images/player/{sofascore_id}.png",
        }

        jugador, created = Jugador.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults=defaults
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

            logger.info(f"\n📅 Sincronizando {len(eventos)} partidos del {fecha.strftime('%Y-%m-%d')}...")

            for evento in eventos:
                await self.sync_partido(evento)

            logger.info(f"✓ Completado: {len(eventos)} partidos sincronizados")

        except Exception as e:
            logger.error(f"✗ Error sincronizando partidos de {fecha}: {e}")
            self.errores.append(f"Fecha {fecha}: {e}")

    async def sync_partido(self, evento_data: Dict) -> Optional[Partido]:
        """Sincronizar un partido"""
        try:
            sofascore_id = evento_data.get('id')
            if not sofascore_id:
                return None

            # Sincronizar datos relacionados
            torneo_data = evento_data.get('tournament', {})

            # País y liga
            pais = None
            categoria = torneo_data.get('category', {})
            if categoria.get('country'):
                pais = await self.sync_pais(categoria['country'])
            elif categoria.get('name'):
                # Para torneos internacionales sin país específico
                pais_data = {'name': categoria['name'], 'alpha2': categoria.get('alpha2', '')}
                pais = await self.sync_pais(pais_data)

            liga = await self.sync_liga(torneo_data.get('uniqueTournament', torneo_data), pais)
            if not liga:
                logger.warning(f"  ⚠ No se pudo crear liga para partido {sofascore_id}")
                return None

            # Temporada
            season_data = evento_data.get('season', {})
            temporada = await self.sync_temporada(season_data, liga)
            if not temporada:
                logger.warning(f"  ⚠ No se pudo crear temporada para partido {sofascore_id}")
                return None

            # Equipos
            equipo_local = await self.sync_equipo(evento_data.get('homeTeam', {}))
            equipo_visitante = await self.sync_equipo(evento_data.get('awayTeam', {}))

            if not equipo_local or not equipo_visitante:
                logger.warning(f"  ⚠ No se pudieron crear equipos para partido {sofascore_id}")
                return None

            # Estado del partido
            status = evento_data.get('status', {})
            estado_map = {
                'notstarted': 'notstarted',
                'inprogress': 'inprogress',
                'finished': 'finished',
                'postponed': 'postponed',
                'cancelled': 'cancelled',
                'abandoned': 'abandoned',
                'interrupted': 'interrupted',
                'suspended': 'suspended'
            }
            estado = estado_map.get(status.get('type', 'notstarted'), 'notstarted')

            # Fecha y hora
            timestamp = evento_data.get('startTimestamp', 0)
            fecha_hora = datetime.fromtimestamp(timestamp)
            if timezone.is_naive(fecha_hora):
                fecha_hora = timezone.make_aware(fecha_hora)

            # Crear partido
            partido = await self._crear_partido(
                sofascore_id, liga, temporada, equipo_local, equipo_visitante,
                fecha_hora, timestamp, evento_data, estado, status
            )

            # Sincronizar detalles si está finalizado o en progreso
            if estado in ['finished', 'inprogress'] and partido:
                await self.sync_detalles_partido(sofascore_id, partido)

            return partido

        except Exception as e:
            logger.error(f"  ✗ Error sincronizando partido {evento_data.get('id')}: {e}")
            self.errores.append(f"Partido {evento_data.get('id')}: {e}")
            return None

    @sync_to_async
    def _crear_partido(self, sofascore_id, liga, temporada, equipo_local,
                       equipo_visitante, fecha_hora, timestamp, evento_data, estado, status):
        """Crear o actualizar partido en la BD"""

        # Marcadores
        home_score = evento_data.get('homeScore', {})
        away_score = evento_data.get('awayScore', {})

        defaults = {
            'liga': liga,
            'temporada': temporada,
            'equipo_local': equipo_local,
            'equipo_visitante': equipo_visitante,
            'fecha_hora': fecha_hora,
            'fecha_hora_timestamp': timestamp,
            'custom_id': evento_data.get('customId', ''),
            'slug': evento_data.get('slug', ''),
            'goles_local': home_score.get('current'),
            'goles_visitante': away_score.get('current'),
            'goles_local_ht': home_score.get('period1'),
            'goles_visitante_ht': away_score.get('period1'),
            'estado': estado,
            'estado_codigo': status.get('code'),
            'estado_descripcion': status.get('description', ''),
            'ronda': evento_data.get('roundInfo', {}).get('name', ''),
        }

        # Información adicional si está disponible
        if evento_data.get('winnerCode'):
            if evento_data['winnerCode'] == 1:
                defaults['ganador'] = equipo_local
            elif evento_data['winnerCode'] == 2:
                defaults['ganador'] = equipo_visitante

        partido, created = Partido.objects.update_or_create(
            sofascore_id=sofascore_id,
            defaults=defaults
        )

        if created:
            self.stats['partidos'] += 1
            logger.info(f"  ✓ Partido: {equipo_local.nombre} vs {equipo_visitante.nombre}")

        return partido

    async def sync_detalles_partido(self, event_id: int, partido: Partido):
        """Sincronizar detalles del partido (estadísticas, eventos, alineaciones)"""
        try:
            # Sincronizar en paralelo para mayor eficiencia
            await asyncio.gather(
                self.sync_estadisticas_partido(event_id, partido),
                self.sync_eventos_partido(event_id, partido),
                self.sync_alineaciones_partido(event_id, partido),
                return_exceptions=True
            )

            # Actualizar flags
            await self._actualizar_flags_partido(partido)

        except Exception as e:
            logger.warning(f"  ⚠ Error en detalles del partido {event_id}: {e}")

    @sync_to_async
    def _actualizar_flags_partido(self, partido: Partido):
        """Actualizar flags de información disponible"""
        partido.tiene_estadisticas = partido.estadisticas.exists()
        partido.tiene_incidentes = partido.eventos.exists()
        partido.tiene_lineups = partido.alineaciones.exists()
        partido.save(update_fields=['tiene_estadisticas', 'tiene_incidentes', 'tiene_lineups'])

    async def sync_estadisticas_partido(self, event_id: int, partido: Partido):
        """Sincronizar estadísticas del partido"""
        try:
            data = await self.api.get_partido_estadisticas(event_id)

            for grupo in data.get('statistics', []):
                periodo = self._mapear_periodo(grupo.get('period', 'ALL'))

                # Extraer estadísticas
                stats_items = {}
                for group in grupo.get('groups', []):
                    for stat in group.get('statisticsItems', []):
                        nombre = stat.get('name')
                        stats_items[nombre] = {
                            'home': stat.get('home'),
                            'away': stat.get('away'),
                            'homeTotal': stat.get('homeTotal'),
                            'awayTotal': stat.get('awayTotal'),
                        }

                await self._crear_estadistica(partido, periodo, stats_items)

            self.stats['estadisticas'] += 1

        except Exception as e:
            logger.debug(f"    ⚠ No hay estadísticas disponibles: {e}")

    def _mapear_periodo(self, periodo_str: str) -> str:
        """Mapear período de Sofascore a modelo"""
        mapeo = {
            'ALL': 'ALL',
            '1ST': '1H',
            '2ND': '2H',
            'FIRST_HALF': '1H',
            'SECOND_HALF': '2H',
            '1H': '1H',
            '2H': '2H',
        }
        return mapeo.get(periodo_str, 'ALL')

    @sync_to_async
    def _crear_estadistica(self, partido: Partido, periodo: str, stats: Dict):
        """Crear o actualizar estadística en BD"""
        defaults = {
            'posesion_local': self._parse_float(stats.get('Ball possession', {}).get('home')),
            'posesion_visitante': self._parse_float(stats.get('Ball possession', {}).get('away')),
            'tiros_local': self._parse_int(stats.get('Total shots', {}).get('home')),
            'tiros_visitante': self._parse_int(stats.get('Total shots', {}).get('away')),
            'tiros_puerta_local': self._parse_int(stats.get('Shots on target', {}).get('home')),
            'tiros_puerta_visitante': self._parse_int(stats.get('Shots on target', {}).get('away')),
            'tiros_fuera_local': self._parse_int(stats.get('Shots off target', {}).get('home')),
            'tiros_fuera_visitante': self._parse_int(stats.get('Shots off target', {}).get('away')),
            'tiros_bloqueados_local': self._parse_int(stats.get('Blocked shots', {}).get('home')),
            'tiros_bloqueados_visitante': self._parse_int(stats.get('Blocked shots', {}).get('away')),
            'corners_local': self._parse_int(stats.get('Corner kicks', {}).get('home')),
            'corners_visitante': self._parse_int(stats.get('Corner kicks', {}).get('away')),
            'faltas_local': self._parse_int(stats.get('Fouls', {}).get('home')),
            'faltas_visitante': self._parse_int(stats.get('Fouls', {}).get('away')),
            'tarjetas_amarillas_local': self._parse_int(stats.get('Yellow cards', {}).get('home')),
            'tarjetas_amarillas_visitante': self._parse_int(stats.get('Yellow cards', {}).get('away')),
            'tarjetas_rojas_local': self._parse_int(stats.get('Red cards', {}).get('home')),
            'tarjetas_rojas_visitante': self._parse_int(stats.get('Red cards', {}).get('away')),
            'fueras_juego_local': self._parse_int(stats.get('Offsides', {}).get('home')),
            'fueras_juego_visitante': self._parse_int(stats.get('Offsides', {}).get('away')),
            'estadisticas_adicionales': {k: v for k, v in stats.items() if k not in [
                'Ball possession', 'Total shots', 'Shots on target', 'Shots off target',
                'Blocked shots', 'Corner kicks', 'Fouls', 'Yellow cards', 'Red cards', 'Offsides'
            ]}
        }

        EstadisticaPartido.objects.update_or_create(
            partido=partido,
            periodo=periodo,
            defaults=defaults
        )

    async def sync_eventos_partido(self, event_id: int, partido: Partido):
        """Sincronizar eventos del partido"""
        try:
            data = await self.api.get_partido_incidentes(event_id)
            incidents = data.get('incidents', [])
            await self._crear_eventos(partido, incidents)
            self.stats['eventos'] += len(incidents)
        except Exception as e:
            logger.debug(f"    ⚠ No hay incidentes disponibles: {e}")

    @sync_to_async
    def _crear_eventos(self, partido: Partido, incidents: List[Dict]):
        """Crear eventos en BD"""
        # Limpiar eventos anteriores
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

            # Buscar jugador
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

        # Crear todos los eventos de una vez
        if eventos_crear:
            EventoPartido.objects.bulk_create(eventos_crear, ignore_conflicts=True)

    async def sync_alineaciones_partido(self, event_id: int, partido: Partido):
        """Sincronizar alineaciones del partido"""
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
            logger.debug(f"    ⚠ No hay alineaciones disponibles: {e}")

    @sync_to_async
    def _limpiar_alineaciones(self, partido: Partido):
        """Limpiar alineaciones anteriores"""
        Alineacion.objects.filter(partido=partido).delete()

    @sync_to_async
    def _sync_alineacion_equipo(self, data: Dict, partido: Partido, equipo: Equipo, es_local: bool):
        """Sincronizar alineación de un equipo"""
        alineaciones_crear = []

        for player_data in data.get('players', []):
            player_info = player_data.get('player', {})
            try:
                jugador = Jugador.objects.get(sofascore_id=player_info['id'])

                # Estadísticas del jugador
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
                logger.debug(f"      Jugador {player_info.get('id')} no encontrado")
                continue

        if alineaciones_crear:
            Alineacion.objects.bulk_create(alineaciones_crear, ignore_conflicts=True)
            self.stats['alineaciones'] += len(alineaciones_crear)

    # ============================================
    # MÉTODOS DE SINCRONIZACIÓN MASIVA
    # ============================================

    async def sync_liga_completa(self, tournament_id: int, season_id: int, max_partidos: int = None):
        """Sincronizar liga completa con límite opcional de partidos"""
        try:
            logger.info(f"\n🏆 Sincronizando liga {tournament_id}, temporada {season_id}...")

            # Obtener información de la liga
            torneo_data = await self.api.get_torneo_info(tournament_id)
            liga = await self.sync_liga(torneo_data.get('uniqueTournament', {}))

            # Obtener información de la temporada
            season_data = await self.api.get_info_temporada_info(tournament_id, season_id)
            temporada = await self.sync_temporada(season_data.get('info', {}).get('season', {}), liga)

            # Sincronizar equipos de la temporada
            await self.sync_equipos_temporada(tournament_id, season_id)

            # Obtener partidos
            partidos_data = await self.api.get_torneo_partidos(tournament_id, season_id)
            eventos = partidos_data.get('events', [])

            if max_partidos:
                eventos = eventos[:max_partidos]

            logger.info(f"📊 Encontrados {len(eventos)} partidos")

            # Sincronizar partidos con barra de progreso
            for i, evento in enumerate(eventos, 1):
                logger.info(f"  [{i}/{len(eventos)}] ", end='')
                await self.sync_partido(evento)

                # Pausa cada 10 partidos para no sobrecargar
                if i % 10 == 0:
                    await asyncio.sleep(1)

            logger.info(f"✅ Liga sincronizada: {liga.nombre}")

        except Exception as e:
            logger.error(f"✗ Error sincronizando liga: {e}")
            import traceback
            traceback.print_exc()
            self.errores.append(f"Liga {tournament_id}: {e}")

    async def sync_equipos_temporada(self, tournament_id: int, season_id: int):
        """Sincronizar todos los equipos de una temporada"""
        try:
            data = await self.api.get_equipos_temporada_info(tournament_id, season_id)
            equipos_data = data.get('teams', [])

            logger.info(f"📋 Sincronizando {len(equipos_data)} equipos...")

            for team_data in equipos_data:
                await self.sync_equipo(team_data.get('team', {}))

            logger.info(f"✓ Equipos sincronizados")

        except Exception as e:
            logger.warning(f"⚠ Error sincronizando equipos: {e}")

    async def sync_partidos_rango_fechas(self, fecha_inicio: datetime, fecha_fin: datetime):
        """Sincronizar rango de fechas"""
        fecha_actual = fecha_inicio

        while fecha_actual <= fecha_fin:
            await self.sync_partidos_fecha(fecha_actual)
            fecha_actual += timedelta(days=1)
            await asyncio.sleep(1)  # Pausa entre días

    # ============================================
    # MÉTODOS AUXILIARES
    # ============================================

    def _parse_int(self, value) -> int:
        """Convertir a int de forma segura"""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value) -> Optional[float]:
        """Convertir a float de forma segura"""
        try:
            if isinstance(value, str):
                value = value.rstrip('%')
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def print_stats(self):
        """Imprimir estadísticas de sincronización"""
        print("\n" + "=" * 60)
        print("📊 ESTADÍSTICAS DE SINCRONIZACIÓN")
        print("=" * 60)
        for key, value in self.stats.items():
            if value > 0:
                print(f"  {key.capitalize():.<30} {value:>5}")

        if self.errores:
            print("\n" + "=" * 60)
            print(f"⚠️  ERRORES ENCONTRADOS ({len(self.errores)})")
            print("=" * 60)
            for i, error in enumerate(self.errores[:10], 1):  # Mostrar solo los primeros 10
                print(f"  {i}. {error}")
            if len(self.errores) > 10:
                print(f"  ... y {len(self.errores) - 10} errores más")

        print("=" * 60)


# ============================================
# FUNCIONES PRINCIPALES DE SINCRONIZACIÓN
# ============================================

async def sync_partidos_hoy():
    """Sincronizar partidos de hoy"""
    manager = SofascoreSyncManager()
    try:
        await manager.sync_partidos_fecha(datetime.now())
        manager.print_stats()
    finally:
        await manager.close()


async def sync_partidos_ayer():
    """Sincronizar partidos de ayer"""
    manager = SofascoreSyncManager()
    try:
        ayer = datetime.now() - timedelta(days=1)
        await manager.sync_partidos_fecha(ayer)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_liga_espanola(max_partidos: int = None):
    """Sincronizar La Liga Española"""
    manager = SofascoreSyncManager()
    try:
        # La Liga - Temporada 2024/25
        await manager.sync_liga_completa(8, 61643, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_premier_league(max_partidos: int = None):
    """Sincronizar Premier League"""
    manager = SofascoreSyncManager()
    try:
        # Premier League - Temporada 2024/25
        await manager.sync_liga_completa(17, 61627, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_champions_league(max_partidos: int = None):
    """Sincronizar Champions League"""
    manager = SofascoreSyncManager()
    try:
        # Champions League - Temporada 2024/25
        await manager.sync_liga_completa(7, 52162, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_serie_a(max_partidos: int = None):
    """Sincronizar Serie A de Italia"""
    manager = SofascoreSyncManager()
    try:
        # Serie A - Temporada 2024/25
        await manager.sync_liga_completa(23, 61644, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_bundesliga(max_partidos: int = None):
    """Sincronizar Bundesliga Alemana"""
    manager = SofascoreSyncManager()
    try:
        # Bundesliga - Temporada 2024/25
        await manager.sync_liga_completa(35, 61628, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_ligue1(max_partidos: int = None):
    """Sincronizar Ligue 1 Francesa"""
    manager = SofascoreSyncManager()
    try:
        # Ligue 1 - Temporada 2024/25
        await manager.sync_liga_completa(34, 61645, max_partidos)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_ultima_semana():
    """Sincronizar última semana de partidos"""
    manager = SofascoreSyncManager()
    try:
        hoy = datetime.now()
        hace_semana = hoy - timedelta(days=7)
        await manager.sync_partidos_rango_fechas(hace_semana, hoy)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_top5_ligas(max_partidos: int = 50):
    """Sincronizar las 5 grandes ligas europeas"""
    manager = SofascoreSyncManager()
    try:
        logger.info("\n🌍 Sincronizando TOP 5 Ligas Europeas...")

        ligas = [
            (17, 61627, "Premier League"),
            (8, 61643, "La Liga"),
            (23, 61644, "Serie A"),
            (35, 61628, "Bundesliga"),
            (34, 61645, "Ligue 1"),
        ]

        for tournament_id, season_id, nombre in ligas:
            logger.info(f"\n{'='*60}")
            logger.info(f"Sincronizando {nombre}...")
            logger.info(f"{'='*60}")
            await manager.sync_liga_completa(tournament_id, season_id, max_partidos)
            await asyncio.sleep(2)  # Pausa entre ligas

        manager.print_stats()
    finally:
        await manager.close()


async def sync_equipo_especifico(team_id: int):
    """Sincronizar un equipo específico con todos sus datos"""
    manager = SofascoreSyncManager()
    try:
        logger.info(f"\n👕 Sincronizando equipo {team_id}...")
        await manager.sync_equipo_completo(team_id)
        manager.print_stats()
    finally:
        await manager.close()


async def sync_partido_especifico(event_id: int):
    """Sincronizar un partido específico con todos sus detalles"""
    manager = SofascoreSyncManager()
    try:
        logger.info(f"\n⚽ Sincronizando partido {event_id}...")

        # Obtener datos del partido
        evento_data = await manager.api.get_partido_detalles(event_id)
        partido = await manager.sync_partido(evento_data.get('event', {}))

        if partido:
            logger.info("✓ Partido sincronizado exitosamente")

        manager.print_stats()
    finally:
        await manager.close()


# ============================================
# MENÚ INTERACTIVO
# ============================================

def mostrar_menu():
    """Mostrar menú de opciones"""
    print("\n" + "=" * 60)
    print("⚽ SINCRONIZADOR DE SOFASCORE - DJANGO")
    print("=" * 60)
    print("\n📅 PARTIDOS POR FECHA:")
    print("  1. Sincronizar partidos de hoy")
    print("  2. Sincronizar partidos de ayer")
    print("  3. Sincronizar última semana")

    print("\n🏆 LIGAS COMPLETAS:")
    print("  4. La Liga Española")
    print("  5. Premier League")
    print("  6. Champions League")
    print("  7. Serie A (Italia)")
    print("  8. Bundesliga (Alemania)")
    print("  9. Ligue 1 (Francia)")
    print(" 10. TOP 5 Ligas Europeas (limitado)")

    print("\n🔍 BÚSQUEDA ESPECÍFICA:")
    print(" 11. Sincronizar equipo específico (por ID)")
    print(" 12. Sincronizar partido específico (por ID)")

    print("\n⚙️  OPCIONES:")
    print(" 13. Salir")
    print("\n" + "=" * 60)


async def ejecutar_opcion(opcion: str):
    """Ejecutar la opción seleccionada"""

    if opcion == '1':
        await sync_partidos_hoy()

    elif opcion == '2':
        await sync_partidos_ayer()

    elif opcion == '3':
        await sync_ultima_semana()

    elif opcion == '4':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_liga_espanola(max_partidos)

    elif opcion == '5':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_premier_league(max_partidos)

    elif opcion == '6':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_champions_league(max_partidos)

    elif opcion == '7':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_serie_a(max_partidos)

    elif opcion == '8':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_bundesliga(max_partidos)

    elif opcion == '9':
        max_partidos = input("¿Límite de partidos? (Enter para todos): ").strip()
        max_partidos = int(max_partidos) if max_partidos else None
        await sync_ligue1(max_partidos)

    elif opcion == '10':
        max_partidos = input("¿Partidos por liga? (default 50): ").strip()
        max_partidos = int(max_partidos) if max_partidos else 50
        await sync_top5_ligas(max_partidos)

    elif opcion == '11':
        team_id = input("ID del equipo: ").strip()
        if team_id.isdigit():
            await sync_equipo_especifico(int(team_id))
        else:
            print("❌ ID inválido")

    elif opcion == '12':
        event_id = input("ID del partido: ").strip()
        if event_id.isdigit():
            await sync_partido_especifico(int(event_id))
        else:
            print("❌ ID inválido")

    elif opcion == '13':
        print("\n¡Hasta luego! 👋\n")
        return False

    else:
        print("\n❌ Opción no válida")

    return True


async def main():
    """Función principal con menú interactivo"""
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción: ").strip()

        continuar = await ejecutar_opcion(opcion)
        if not continuar:
            break

        input("\nPresiona Enter para continuar...")


# ============================================
# EJECUCIÓN DIRECTA
# ============================================

if __name__ == "__main__":
    # Puedes ejecutar funciones específicas directamente:

    # Para menú interactivo:
    asyncio.run(main())

    # O descomentar alguna de estas para ejecución directa:
    # asyncio.run(sync_partidos_hoy())
    # asyncio.run(sync_liga_espanola(max_partidos=10))
    # asyncio.run(sync_top5_ligas(max_partidos=20))