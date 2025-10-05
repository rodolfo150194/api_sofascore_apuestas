from django.contrib import admin
from django.contrib import admin

from futbol.models import *


@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo']
    search_fields = ['nombre']

@admin.register(Liga)
class LigaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'pais', 'tipo', 'nivel']
    list_filter = ['tipo', 'pais']
    search_fields = ['nombre']

@admin.register(Temporada)
class TemporadaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'liga', 'año_inicio', 'activa']
    list_filter = ['activa', 'liga']

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'nombre_corto', 'ciudad', 'pais']
    search_fields = ['nombre', 'ciudad']
    list_filter = ['pais']

@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'equipo', 'posicion', 'numero_camiseta', 'nacionalidad']
    search_fields = ['nombre', 'nombre_completo']
    list_filter = ['posicion', 'equipo']

@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'liga', 'fecha_hora', 'estado']
    list_filter = ['estado', 'liga', 'fecha_hora']
    search_fields = ['equipo_local__nombre', 'equipo_visitante__nombre']
    date_hierarchy = 'fecha_hora'

@admin.register(EstadisticaPartido)
class EstadisticaPartidoAdmin(admin.ModelAdmin):
    list_display = ['partido', 'periodo', 'posesion_local', 'posesion_visitante']
    list_filter = ['periodo']

@admin.register(EventoPartido)
class EventoPartidoAdmin(admin.ModelAdmin):
    list_display = ['partido', 'tipo', 'jugador', 'minuto', 'es_local']
    list_filter = ['tipo', 'es_local']

@admin.register(Alineacion)
class AlineacionAdmin(admin.ModelAdmin):
    list_display = ['jugador', 'partido', 'es_titular', 'rating', 'goles', 'asistencias']
    list_filter = ['es_titular', 'es_local']

@admin.register(EstadisticaJugador)
class EstadisticaJugadorAdmin(admin.ModelAdmin):
    list_display = ['jugador', 'temporada', 'partidos_jugados', 'goles', 'asistencias']
    list_filter = ['temporada']
