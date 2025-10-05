"""
Utilidades para trabajar con los datos de Sofascore
Ubicar en: futbol/utils.py
"""

from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from typing import List, Dict, Optional

from futbol.models import *


class EstadisticasEquipo:
    """Clase para calcular estadísticas de equipos"""

    def __init__(self, equipo: Equipo, temporada: Optional[Temporada] = None):
        self.equipo = equipo
        self.temporada = temporada

    def partidos_query(self):
        """Query base de partidos del equipo"""
        query = Partido.objects.filter(
            Q(equipo_local=self.equipo) | Q(equipo_visitante=self.equipo),
            estado='finished'
        )
        if self.temporada:
            query = query.filter(temporada=self.temporada)
        return query

    def estadisticas_generales(self) -> Dict:
        """Obtener estadísticas generales del equipo"""
        partidos = self.partidos_query()

        victorias = 0
        empates = 0
        derrotas = 0
        goles_favor = 0
        goles_contra = 0

        for partido in partidos:
            es_local = partido.equipo_local == self.equipo

            if es_local:
                goles_favor += partido.goles_local or 0
                goles_contra += partido.goles_visitante or 0
                resultado = partido.resultado
                if resultado == 'L':
                    victorias += 1
                elif resultado == 'E':
                    empates += 1
                elif resultado == 'V':
                    derrotas += 1
            else:
                goles_favor += partido.goles_visitante or 0
                goles_contra += partido.goles_local or 0
                resultado = partido.resultado
                if resultado == 'V':
                    victorias += 1
                elif resultado == 'E':
                    empates += 1
                elif resultado == 'L':
                    derrotas += 1

        partidos_jugados = victorias + empates + derrotas
        puntos = victorias * 3 + empates

        return {
            'partidos_jugados': partidos_jugados,
            'victorias': victorias,
            'empates': empates,
            'derrotas': derrotas,
            'goles_favor': goles_favor,
            'goles_contra': goles_contra,
            'diferencia_goles': goles_favor - goles_contra,
            'puntos': puntos,
            'promedio_puntos': round(puntos / partidos_jugados, 2) if partidos_jugados > 0 else 0,
            'promedio_goles_favor': round(goles_favor / partidos_jugados, 2) if partidos_jugados > 0 else 0,
            'promedio_goles_contra': round(goles_contra / partidos_jugados, 2) if partidos_jugados > 0 else 0,
        }

    def racha_actual(self, cantidad: int = 5) -> List[str]:
        """Obtener racha de resultados recientes"""
        partidos = self.partidos_query().order_by('-fecha_hora')[:cantidad]

        racha = []
        for partido in reversed(list(partidos)):
            es_local = partido.equipo_local == self.equipo
            resultado = partido.resultado

            if es_local:
                if resultado == 'L':
                    racha.append('V')
                elif resultado == 'E':
                    racha.append('E')
                elif resultado == 'V':
                    racha.append('D')
            else:
                if resultado == 'V':
                    racha.append('V')
                elif resultado == 'E':
                    racha.append('E')
                elif resultado == 'L':
                    racha.append('D')

        return racha

    def estadisticas_local_visitante(self) -> Dict:
        """Estadísticas separadas de local y visitante"""
        local = self._estadisticas_por_localidad(True)
        visitante = self._estadisticas_por_localidad(False)

        return {
            'local': local,
            'visitante': visitante
        }

    def _estadisticas_por_localidad(self, es_local: bool) -> Dict:
        """Calcular estadísticas para local o visitante"""
        if es_local:
            partidos = Partido.objects.filter(
                equipo_local=self.equipo,
                estado='finished'
            )
        else:
            partidos = Partido.objects.filter(
                equipo_visitante=self.equipo,
                estado='finished'
            )

        if self.temporada:
            partidos = partidos.filter(temporada=self.temporada)

        victorias = empates = derrotas = 0
        goles_favor = goles_contra = 0

        for partido in partidos:
            if es_local:
                goles_favor += partido.goles_local or 0
                goles_contra += partido.goles_visitante or 0
                if partido.resultado == 'L':
                    victorias += 1
                elif partido.resultado == 'E':
                    empates += 1
                elif partido.resultado == 'V':
                    derrotas += 1
            else:
                goles_favor += partido.goles_visitante or 0
                goles_contra += partido.goles_local or 0
                if partido.resultado == 'V':
                    victorias += 1
                elif partido.resultado == 'E':
                    empates += 1
                elif partido.resultado == 'L':
                    derrotas += 1

        partidos_jugados = victorias + empates + derrotas

        return {
            'partidos': partidos_jugados,
            'victorias': victorias,
            'empates': empates,
            'derrotas': derrotas,
            'goles_favor': goles_favor,
            'goles_contra': goles_contra,
            'puntos': victorias * 3 + empates
        }


class AnalisisPartido:
    """Clase para análisis de partidos"""

    def __init__(self, partido: Partido):
        self.partido = partido

    def resumen_completo(self) -> Dict:
        """Obtener resumen completo del partido"""
        return {
            'info_basica': self._info_basica(),
            'marcador': self._marcador(),
            'estadisticas': self._estadisticas_resumen(),
            'eventos': self._eventos_resumen(),
            'alineaciones': self._alineaciones_resumen()
        }

    def _info_basica(self) -> Dict:
        """Información básica del partido"""
        return {
            'id': self.partido.sofascore_id,
            'liga': self.partido.liga.nombre,
            'temporada': self.partido.temporada.nombre,
            'fecha': self.partido.fecha_hora,
            'estado': self.partido.get_estado_display(),
            'estadio': self.partido.estadio,
            'arbitro': self.partido.arbitro,
        }

    def _marcador(self) -> Dict:
        """Información del marcador"""
        return {
            'local': {
                'equipo': self.partido.equipo_local.nombre,
                'goles': self.partido.goles_local,
                'goles_ht': self.partido.goles_local_ht,
            },
            'visitante': {
                'equipo': self.partido.equipo_visitante.nombre,
                'goles': self.partido.goles_visitante,
                'goles_ht': self.partido.goles_visitante_ht,
            },
            'resultado': self.partido.resultado
        }

    def _estadisticas_resumen(self) -> Optional[Dict]:
        """Resumen de estadísticas"""
        try:
            stats = self.partido.estadisticas.get(periodo='ALL')
            return {
                'posesion': {
                    'local': stats.posesion_local,
                    'visitante': stats.posesion_visitante
                },
                'tiros': {
                    'local': stats.tiros_local,
                    'visitante': stats.tiros_visitante
                },
                'tiros_puerta': {
                    'local': stats.tiros_puerta_local,
                    'visitante': stats.tiros_puerta_visitante
                },
                'corners': {
                    'local': stats.corners_local,
                    'visitante': stats.corners_visitante
                }
            }
        except EstadisticaPartido.DoesNotExist:
            return None

    def _eventos_resumen(self) -> List[Dict]:
        """Resumen de eventos importantes"""
        eventos = self.partido.eventos.filter(
            tipo__in=['goal', 'own_goal', 'red_card', 'penalty']
        ).order_by('minuto')

        return [{
            'tipo': evento.get_tipo_display(),
            'minuto': evento.minuto,
            'jugador': evento.jugador.nombre if evento.jugador else None,
            'es_local': evento.es_local
        } for evento in eventos]

    def _alineaciones_resumen(self) -> Dict:
        """Resumen de alineaciones"""
        return {
            'local': self.partido.alineaciones.filter(es_local=True, es_titular=True).count(),
            'visitante': self.partido.alineaciones.filter(es_local=False, es_titular=True).count(),
        }


class TopScorers:
    """Obtener tabla de goleadores"""

    def __init__(self, temporada: Temporada, liga: Optional[Liga] = None):
        self.temporada = temporada
        self.liga = liga or temporada.liga

    def obtener_goleadores(self, limite: int = 20) -> List[Dict]:
        """Obtener top goleadores"""
        # Método 1: Desde EstadisticaJugador
        stats = EstadisticaJugador.objects.filter(
            temporada=self.temporada
        ).select_related('jugador', 'jugador__equipo').order_by('-goles')[:limite]

        return [{
            'posicion': i + 1,
            'jugador': stat.jugador.nombre,
            'equipo': stat.jugador.equipo.nombre if stat.jugador.equipo else 'N/A',
            'goles': stat.goles,
            'asistencias': stat.asistencias,
            'partidos': stat.partidos_jugados,
            'promedio': stat.goles_por_partido
        } for i, stat in enumerate(stats)]

    def obtener_asistentes(self, limite: int = 20) -> List[Dict]:
        """Obtener top asistidores"""
        stats = EstadisticaJugador.objects.filter(
            temporada=self.temporada
        ).select_related('jugador', 'jugador__equipo').order_by('-asistencias')[:limite]

        return [{
            'posicion': i + 1,
            'jugador': stat.jugador.nombre,
            'equipo': stat.jugador.equipo.nombre if stat.jugador.equipo else 'N/A',
            'asistencias': stat.asistencias,
            'goles': stat.goles,
            'partidos': stat.partidos_jugados,
        } for i, stat in enumerate(stats)]


class CalculadoraTabla:
    """Calcular tabla de posiciones"""

    def __init__(self, temporada: Temporada):
        self.temporada = temporada

    def calcular_tabla(self) -> List[Dict]:
        """Calcular tabla de posiciones completa"""
        # Obtener todos los equipos que jugaron en la temporada
        equipos_ids = set()
        partidos = Partido.objects.filter(
            temporada=self.temporada,
            estado='finished'
        )

        for partido in partidos:
            equipos_ids.add(partido.equipo_local.id)
            equipos_ids.add(partido.equipo_visitante.id)

        equipos = Equipo.objects.filter(id__in=equipos_ids)

        tabla = []
        for equipo in equipos:
            stats = EstadisticasEquipo(equipo, self.temporada)
            datos = stats.estadisticas_generales()

            tabla.append({
                'equipo': equipo.nombre,
                'equipo_obj': equipo,
                **datos
            })

        # Ordenar por puntos, diferencia de goles y goles a favor
        tabla.sort(
            key=lambda x: (x['puntos'], x['diferencia_goles'], x['goles_favor']),
            reverse=True
        )

        # Agregar posición
        for i, equipo_data in enumerate(tabla, 1):
            equipo_data['posicion'] = i

        return tabla


class ProximosPartidosRecomendador:
    """Recomendar partidos próximos interesantes"""

    def __init__(self):
        pass

    def partidos_destacados(self, dias: int = 7, limite: int = 10) -> List[Partido]:
        """Obtener partidos destacados de los próximos días"""
        fecha_inicio = timezone.now()
        fecha_fin = fecha_inicio + timedelta(days=dias)

        partidos = Partido.objects.filter(
            estado='notstarted',
            fecha_hora__gte=fecha_inicio,
            fecha_hora__lte=fecha_fin
        ).select_related(
            'equipo_local',
            'equipo_visitante',
            'liga'
        ).order_by('fecha_hora')

        # Filtrar por ligas importantes
        ligas_importantes = Liga.objects.filter(
            tipo__in=['liga', 'internacional'],
            nivel=1
        ).values_list('id', flat=True)

        partidos_filtrados = partidos.filter(liga_id__in=ligas_importantes)[:limite]

        return list(partidos_filtrados)


# ==================================================
# FUNCIONES DE UTILIDAD
# ==================================================

def obtener_estadisticas_liga(temporada: Temporada) -> Dict:
    """Obtener estadísticas generales de una liga"""
    partidos = Partido.objects.filter(
        temporada=temporada,
        estado='finished'
    )

    total_partidos = partidos.count()
    total_goles = sum(
        (p.goles_local or 0) + (p.goles_visitante or 0)
        for p in partidos
    )

    return {
        'temporada': temporada.nombre,
        'liga': temporada.liga.nombre,
        'total_partidos': total_partidos,
        'total_goles': total_goles,
        'promedio_goles': round(total_goles / total_partidos, 2) if total_partidos > 0 else 0,
    }


def buscar_enfrentamientos_directos(equipo1: Equipo, equipo2: Equipo, limite: int = 10) -> List[Partido]:
    """Buscar historial de enfrentamientos entre dos equipos"""
    partidos = Partido.objects.filter(
        Q(equipo_local=equipo1, equipo_visitante=equipo2) |
        Q(equipo_local=equipo2, equipo_visitante=equipo1),
        estado='finished'
    ).order_by('-fecha_hora')[:limite]

    return list(partidos)


def estadisticas_jugador_temporada(jugador: Jugador, temporada: Temporada) -> Optional[Dict]:
    """Obtener estadísticas completas de un jugador en una temporada"""
    try:
        stats = EstadisticaJugador.objects.get(
            jugador=jugador,
            temporada=temporada
        )

        return {
            'jugador': jugador.nombre,
            'equipo': jugador.equipo.nombre if jugador.equipo else 'N/A',
            'temporada': temporada.nombre,
            'partidos_jugados': stats.partidos_jugados,
            'partidos_titular': stats.partidos_titular,
            'minutos_jugados': stats.minutos_jugados,
            'goles': stats.goles,
            'asistencias': stats.asistencias,
            'tarjetas_amarillas': stats.tarjetas_amarillas,
            'tarjetas_rojas': stats.tarjetas_rojas,
            'rating_promedio': stats.rating_promedio,
            'goles_por_partido': stats.goles_por_partido,
            'precision_pases': stats.precision_pases_porcentaje,
        }
    except EstadisticaJugador.DoesNotExist:
        return None


def partidos_hoy() -> List[Partido]:
    """Obtener partidos de hoy"""
    hoy = timezone.now().date()
    return Partido.objects.filter(
        fecha_hora__date=hoy
    ).select_related(
        'equipo_local',
        'equipo_visitante',
        'liga'
    ).order_by('fecha_hora')


def partidos_en_vivo() -> List[Partido]:
    """Obtener partidos en vivo"""
    return Partido.objects.filter(
        estado='inprogress'
    ).select_related(
        'equipo_local',
        'equipo_visitante',
        'liga'
    ).order_by('fecha_hora')


def mejores_partidos_semana() -> List[Dict]:
    """Obtener mejores partidos de la semana (por goles)"""
    hace_semana = timezone.now() - timedelta(days=7)

    partidos = Partido.objects.filter(
        estado='finished',
        fecha_hora__gte=hace_semana
    ).select_related(
        'equipo_local',
        'equipo_visitante',
        'liga'
    )

    partidos_con_goles = []
    for partido in partidos:
        total_goles = (partido.goles_local or 0) + (partido.goles_visitante or 0)
        if total_goles > 0:
            partidos_con_goles.append({
                'partido': partido,
                'total_goles': total_goles,
                'local': partido.equipo_local.nombre,
                'visitante': partido.equipo_visitante.nombre,
                'marcador': f"{partido.goles_local}-{partido.goles_visitante}",
                'liga': partido.liga.nombre,
                'fecha': partido.fecha_hora
            })

    # Ordenar por total de goles
    partidos_con_goles.sort(key=lambda x: x['total_goles'], reverse=True)

    return partidos_con_goles[:10]


def exportar_tabla_csv(temporada: Temporada, archivo: str = 'tabla.csv'):
    """Exportar tabla de posiciones a CSV"""
    import csv

    calculadora = CalculadoraTabla(temporada)
    tabla = calculadora.calcular_tabla()

    with open(archivo, 'w', newline='', encoding='utf-8') as f:
        campos = ['posicion', 'equipo', 'partidos_jugados', 'victorias', 'empates',
                  'derrotas', 'goles_favor', 'goles_contra', 'diferencia_goles', 'puntos']
        writer = csv.DictWriter(f, fieldnames=campos)

        writer.writeheader()
        for fila in tabla:
            writer.writerow({k: fila[k] for k in campos})

    print(f"✓ Tabla exportada a {archivo}")


def limpiar_datos_antiguos(dias: int = 365):
    """Limpiar partidos y datos antiguos"""
    fecha_limite = timezone.now() - timedelta(days=dias)

    partidos_antiguos = Partido.objects.filter(
        fecha_hora__lt=fecha_limite,
        estado='finished'
    )

    count = partidos_antiguos.count()

    # Eliminar eventos, estadísticas y alineaciones asociadas
    EventoPartido.objects.filter(partido__in=partidos_antiguos).delete()
    EstadisticaPartido.objects.filter(partido__in=partidos_antiguos).delete()
    Alineacion.objects.filter(partido__in=partidos_antiguos).delete()

    # Eliminar partidos
    partidos_antiguos.delete()

    print(f"✓ Eliminados {count} partidos antiguos y sus datos relacionados")


def resumen_base_datos() -> Dict:
    """Obtener resumen de la base de datos"""
    return {
        'paises': Pais.objects.count(),
        'ligas': Liga.objects.count(),
        'temporadas': Temporada.objects.count(),
        'equipos': Equipo.objects.count(),
        'jugadores': Jugador.objects.count(),
        'partidos': {
            'total': Partido.objects.count(),
            'finalizados': Partido.objects.filter(estado='finished').count(),
            'por_jugar': Partido.objects.filter(estado='notstarted').count(),
            'en_vivo': Partido.objects.filter(estado='inprogress').count(),
        },
        'estadisticas_partido': EstadisticaPartido.objects.count(),
        'eventos': EventoPartido.objects.count(),
        'alineaciones': Alineacion.objects.count(),
        'estadisticas_jugador': EstadisticaJugador.objects.count(),
    }


# ==================================================
# EJEMPLO DE USO
# ==================================================

if __name__ == "__main__":
    # Ejemplo de cómo usar estas utilidades

    # 1. Obtener estadísticas de un equipo
    # equipo = Equipo.objects.get(nombre="Real Madrid")
    # temporada = Temporada.objects.get(liga__nombre="LaLiga", activa=True)
    # stats = EstadisticasEquipo(equipo, temporada)
    # print(stats.estadisticas_generales())
    # print(stats.racha_actual())

    # 2. Análisis de un partido
    # partido = Partido.objects.get(sofascore_id=12345)
    # analisis = AnalisisPartido(partido)
    # print(analisis.resumen_completo())

    # 3. Tabla de posiciones
    # temporada = Temporada.objects.get(liga__nombre="LaLiga", activa=True)
    # calculadora = CalculadoraTabla(temporada)
    # tabla = calculadora.calcular_tabla()
    # for pos in tabla[:5]:  # Top 5
    #     print(f"{pos['posicion']}. {pos['equipo']} - {pos['puntos']} pts")

    # 4. Top goleadores
    # temporada = Temporada.objects.get(liga__nombre="LaLiga", activa=True)
    # top = TopScorers(temporada)
    # goleadores = top.obtener_goleadores(10)
    # for g in goleadores:
    #     print(f"{g['posicion']}. {g['jugador']} ({g['equipo']}) - {g['goles']} goles")

    # 5. Resumen de la base de datos
    # resumen = resumen_base_datos()
    # print(resumen)

    pass