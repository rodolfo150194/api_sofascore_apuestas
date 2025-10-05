from playwright.async_api import async_playwright
import asyncio
from datetime import datetime, timedelta
import pandas as pd

BASE_URL = "https://www.sofascore.com/api/v1"


class SofascoreAPI:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    async def _init_browser(self):
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

    async def _get(self, endpoint):
        await self._init_browser()
        url = f"{BASE_URL}{endpoint}"
        response = await self.page.goto(url)
        if response.status == 200:
            return await response.json()
        else:
            raise Exception(f"Failed to fetch {endpoint}: {response.status}")

    async def _raw_get(self, url):
        await self._init_browser()
        response = await self.page.goto(url)
        if response.status == 200:
            return await response.json()
        else:
            raise Exception(f"Failed to fetch {url}: {response.status}")

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        # ============================================
        # MÉTODOS PARA PARTIDOS
        # ============================================

    async def get_partidos_hoy(self, deporte="football"):
        """
        Obtener partidos del día actual
        Deportes disponibles: football, basketball, tennis, etc.
        """
        hoy = datetime.now().strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{hoy}"
        return await self._get(endpoint)

    async def get_partidos_fecha(self, fecha, deporte="football"):
        """
        Obtener partidos de una fecha específica
        fecha: formato "YYYY-MM-DD" o datetime object
        """
        if isinstance(fecha, datetime):
            fecha = fecha.strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{fecha}"
        return await self._get(endpoint)

    async def get_partidos_en_vivo(self, deporte="football"):
        """
        Obtener partidos en vivo
        """
        endpoint = f"/sport/{deporte}/events/live"
        return await self._get(endpoint)

    async def get_partido_detalles(self, event_id):
        """
        Obtener detalles de un partido específico
        """
        endpoint = f"/event/{event_id}"
        return await self._get(endpoint)

    async def get_partido_estadisticas(self, event_id):
        """
        Obtener estadísticas de un partido
        """
        endpoint = f"/event/{event_id}/statistics"
        return await self._get(endpoint)

    async def get_partido_lineups(self, event_id):
        """
        Obtener alineaciones de un partido
        """
        endpoint = f"/event/{event_id}/lineups"
        return await self._get(endpoint)

    async def get_partido_incidentes(self, event_id):
        """
        Obtener eventos del partido (goles, tarjetas, etc.)
        """
        endpoint = f"/event/{event_id}/incidents"
        return await self._get(endpoint)

        # ============================================
        # MÉTODOS PARA EQUIPOS
        # ============================================

    async def get_equipo_info(self, team_id):
        """
        Obtener información de un equipo
        """
        endpoint = f"/team/{team_id}"
        return await self._get(endpoint)

    async def get_equipo_proximos_partidos(self, team_id):
        """
        Obtener próximos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/next/0"
        return await self._get(endpoint)

    async def get_equipo_ultimos_partidos(self, team_id):
        """
        Obtener últimos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/last/0"
        return await self._get(endpoint)

    async def get_equipo_jugadores(self, team_id):
        """
        Obtener plantilla de un equipo
        """
        endpoint = f"/team/{team_id}/players"
        return await self._get(endpoint)

        # ============================================
        # MÉTODOS PARA TORNEOS/LIGAS
        # ============================================

    async def get_torneo_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/"
        # endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return await self._get(endpoint)

    async def get_info_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return await self._get(endpoint)

    async def get_temporadas_ligas_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/seasons/"
        return await self._get(endpoint)

    async def get_equipos_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/teams"
        return await self._get(endpoint)


    async def get_torneo_tabla(self, tournament_id, season_id):
        """
        Obtener tabla de posiciones de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        return await self._get(endpoint)

    async def get_torneo_partidos(self, tournament_id, season_id):
        """
        Obtener todos los partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/last/0"
        return await self._get(endpoint)

    async def get_torneo_proximos_partidos(self, tournament_id, season_id):
        """
        Obtener próximos partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        return await self._get(endpoint)


    # ============================================
    # FUNCIONES DE UTILIDAD
    # ============================================

    async def formatear_partidos(data):
        """
        Formatea los datos de partidos en un formato legible
        """
        partidos = []
        for evento in data.get('events', []):
            partido = {
                'id': evento.get('id'),
                'local': evento.get('homeTeam', {}).get('name'),
                'visitante': evento.get('awayTeam', {}).get('name'),
                'marcador_local': evento.get('homeScore', {}).get('current'),
                'marcador_visitante': evento.get('awayScore', {}).get('current'),
                'estado': evento.get('status', {}).get('description'),
                'torneo': evento.get('tournament', {}).get('name'),
                'fecha': datetime.fromtimestamp(evento.get('startTimestamp', 0)),
            }
            partidos.append(partido)
        return pd.DataFrame(partidos)
