from django.db import models
from django.utils import timezone
# Create your models here.
class Pais(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, blank=True)
    bandera_url = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name_plural = "Países"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Liga(models.Model):
    TIPO_CHOICES = [
        ('liga', 'Liga'),
        ('copa', 'Copa'),
        ('internacional', 'Internacional'),
    ]

    sofascore_id = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=200)
    pais = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, related_name='ligas')
    logo_url = models.URLField(max_length=500, blank=True)
    nivel = models.IntegerField(default=1, help_text="1=Primera división, 2=Segunda, etc.")
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='liga')

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Temporada(models.Model):
    sofascore_id = models.IntegerField(unique=True)
    liga = models.ForeignKey(Liga, on_delete=models.CASCADE, related_name='temporadas')
    nombre = models.CharField(max_length=50, help_text="Ej: 2024/25")
    año_inicio = models.IntegerField()
    año_fin = models.IntegerField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['-año_inicio']
        unique_together = ['liga', 'año_inicio']

    def __str__(self):
        return f"{self.liga.nombre} - {self.nombre}"


class Equipo(models.Model):
    sofascore_id = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=200)
    nombre_corto = models.CharField(max_length=50, blank=True)
    pais = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, related_name='equipos')
    ciudad = models.CharField(max_length=100, blank=True)
    estadio = models.CharField(max_length=200, blank=True)
    fundacion = models.IntegerField(null=True, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    colores = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def ultimos_partidos(self, cantidad=5):
        """Obtener últimos partidos del equipo"""
        return Partido.objects.filter(
            models.Q(equipo_local=self) | models.Q(equipo_visitante=self),
            estado='finished'
        ).order_by('-fecha_hora')[:cantidad]

    def proximos_partidos(self, cantidad=5):
        """Obtener próximos partidos del equipo"""
        return Partido.objects.filter(
            models.Q(equipo_local=self) | models.Q(equipo_visitante=self),
            estado='notstarted',
            fecha_hora__gte=timezone.now()
        ).order_by('fecha_hora')[:cantidad]


class Jugador(models.Model):
    POSICION_CHOICES = [
        ('POR', 'Portero'),
        ('DEF', 'Defensa'),
        ('MED', 'Mediocampista'),
        ('DEL', 'Delantero'),
    ]

    PIE_CHOICES = [
        ('derecho', 'Derecho'),
        ('izquierdo', 'Izquierdo'),
        ('ambos', 'Ambos'),
    ]

    sofascore_id = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=200)
    nombre_completo = models.CharField(max_length=300, blank=True)
    equipo = models.ForeignKey(Equipo, on_delete=models.SET_NULL, null=True, related_name='jugadores')
    fecha_nacimiento = models.DateField(null=True, blank=True)
    nacionalidad = models.CharField(max_length=100, blank=True)
    posicion = models.CharField(max_length=3, choices=POSICION_CHOICES)
    numero_camiseta = models.IntegerField(null=True, blank=True)
    altura = models.FloatField(null=True, blank=True, help_text="Altura en cm")
    peso = models.FloatField(null=True, blank=True, help_text="Peso en kg")
    pie_preferido = models.CharField(max_length=20, choices=PIE_CHOICES, blank=True)
    foto_url = models.URLField(max_length=500, blank=True)
    valor_mercado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = "Jugadores"

    def __str__(self):
        return self.nombre

    @property
    def edad(self):
        if self.fecha_nacimiento:
            hoy = timezone.now().date()
            return hoy.year - self.fecha_nacimiento.year - (
                    (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None


class Partido(models.Model):
    ESTADO_CHOICES = [
        ('notstarted', 'No iniciado'),
        ('inprogress', 'En progreso'),
        ('finished', 'Finalizado'),
        ('postponed', 'Pospuesto'),
        ('cancelled', 'Cancelado'),
        ('abandoned', 'Abandonado'),
    ]

    sofascore_id = models.IntegerField(unique=True)
    liga = models.ForeignKey(Liga, on_delete=models.CASCADE, related_name='partidos')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE, related_name='partidos')
    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local')
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visitante')

    fecha_hora = models.DateTimeField()
    jornada = models.IntegerField(null=True, blank=True)

    # Marcadores
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visitante = models.IntegerField(null=True, blank=True)
    goles_local_ht = models.IntegerField(null=True, blank=True, help_text="Medio tiempo")
    goles_visitante_ht = models.IntegerField(null=True, blank=True, help_text="Medio tiempo")

    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='notstarted')
    minuto_actual = models.IntegerField(null=True, blank=True)

    # Información adicional
    estadio = models.CharField(max_length=200, blank=True)
    arbitro = models.CharField(max_length=200, blank=True)
    asistencia = models.IntegerField(null=True, blank=True)
    clima = models.JSONField(default=dict, blank=True)

    # Control
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name_plural = "Partidos"

    def __str__(self):
        if self.goles_local is not None and self.goles_visitante is not None:
            return f"{self.equipo_local} {self.goles_local}-{self.goles_visitante} {self.equipo_visitante}"
        return f"{self.equipo_local} vs {self.equipo_visitante}"

    @property
    def resultado(self):
        """Retorna 'L' (local), 'V' (visitante) o 'E' (empate)"""
        if self.goles_local is None or self.goles_visitante is None:
            return None
        if self.goles_local > self.goles_visitante:
            return 'L'
        elif self.goles_local < self.goles_visitante:
            return 'V'
        return 'E'


class EstadisticaPartido(models.Model):
    PERIODO_CHOICES = [
        ('ALL', 'Todo el partido'),
        ('1H', 'Primera mitad'),
        ('2H', 'Segunda mitad'),
    ]

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='estadisticas')
    periodo = models.CharField(max_length=3, choices=PERIODO_CHOICES, default='ALL')

    # Estadísticas local
    posesion_local = models.FloatField(null=True, blank=True)
    tiros_local = models.IntegerField(default=0)
    tiros_puerta_local = models.IntegerField(default=0)
    corners_local = models.IntegerField(default=0)
    faltas_local = models.IntegerField(default=0)
    tarjetas_amarillas_local = models.IntegerField(default=0)
    tarjetas_rojas_local = models.IntegerField(default=0)
    fueras_juego_local = models.IntegerField(default=0)

    # Estadísticas visitante
    posesion_visitante = models.FloatField(null=True, blank=True)
    tiros_visitante = models.IntegerField(default=0)
    tiros_puerta_visitante = models.IntegerField(default=0)
    corners_visitante = models.IntegerField(default=0)
    faltas_visitante = models.IntegerField(default=0)
    tarjetas_amarillas_visitante = models.IntegerField(default=0)
    tarjetas_rojas_visitante = models.IntegerField(default=0)
    fueras_juego_visitante = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Estadísticas de partido"
        unique_together = ['partido', 'periodo']

    def __str__(self):
        return f"Estadísticas {self.partido} - {self.periodo}"


class EventoPartido(models.Model):
    TIPO_CHOICES = [
        ('goal', 'Gol'),
        ('yellow_card', 'Tarjeta amarilla'),
        ('red_card', 'Tarjeta roja'),
        ('substitution', 'Sustitución'),
        ('penalty', 'Penalti'),
        ('own_goal', 'Autogol'),
        ('var', 'VAR'),
    ]

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='eventos')
    jugador = models.ForeignKey(Jugador, on_delete=models.SET_NULL, null=True, related_name='eventos')
    minuto = models.IntegerField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(blank=True)
    es_local = models.BooleanField(default=True)

    class Meta:
        ordering = ['minuto']
        verbose_name_plural = "Eventos de partido"

    def __str__(self):
        return f"{self.get_tipo_display()} - Min {self.minuto}"


class Alineacion(models.Model):
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='alineaciones')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE)
    es_local = models.BooleanField(default=True)
    es_titular = models.BooleanField(default=True)
    posicion = models.CharField(max_length=50, blank=True)
    numero_camiseta = models.IntegerField(null=True, blank=True)
    formacion_posicion = models.CharField(max_length=10, blank=True)

    # Estadísticas del jugador en el partido
    rating = models.FloatField(null=True, blank=True)
    minutos_jugados = models.IntegerField(default=0)
    goles = models.IntegerField(default=0)
    asistencias = models.IntegerField(default=0)
    tarjetas_amarillas = models.IntegerField(default=0)
    tarjetas_rojas = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Alineaciones"
        unique_together = ['partido', 'jugador']

    def __str__(self):
        titular = "Titular" if self.es_titular else "Suplente"
        return f"{self.jugador.nombre} - {titular}"


class EstadisticaJugador(models.Model):
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='estadisticas')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)

    # Estadísticas generales
    partidos_jugados = models.IntegerField(default=0)
    partidos_titular = models.IntegerField(default=0)
    minutos_jugados = models.IntegerField(default=0)
    goles = models.IntegerField(default=0)
    asistencias = models.IntegerField(default=0)
    tarjetas_amarillas = models.IntegerField(default=0)
    tarjetas_rojas = models.IntegerField(default=0)
    rating_promedio = models.FloatField(null=True, blank=True)

    # Estadísticas detalladas
    tiros_totales = models.IntegerField(default=0)
    tiros_puerta = models.IntegerField(default=0)
    pases_completados = models.IntegerField(default=0)
    pases_intentados = models.IntegerField(default=0)
    duelos_ganados = models.IntegerField(default=0)
    duelos_totales = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Estadísticas de jugador"
        unique_together = ['jugador', 'temporada']

    def __str__(self):
        return f"{self.jugador.nombre} - {self.temporada}"

    @property
    def goles_por_partido(self):
        if self.partidos_jugados > 0:
            return round(self.goles / self.partidos_jugados, 2)
        return 0