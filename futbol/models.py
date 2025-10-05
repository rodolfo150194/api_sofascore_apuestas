from django.db import models
from django.utils import timezone


class Pais(models.Model):
    sofascore_id = models.IntegerField(unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, blank=True)
    alpha2 = models.CharField(max_length=2, blank=True)
    alpha3 = models.CharField(max_length=3, blank=True)
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
        ('amistoso', 'Amistoso'),
    ]

    sofascore_id = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=200)
    nombre_corto = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    pais = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, blank=True, related_name='ligas')
    logo_url = models.URLField(max_length=500, blank=True)
    nivel = models.IntegerField(default=1, help_text="1=Primera división, 2=Segunda, etc.")
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='liga')

    # Campos adicionales de Sofascore
    tiene_tabla_posiciones = models.BooleanField(default=True)
    tiene_playoff = models.BooleanField(default=False)
    prioridad = models.IntegerField(default=0, help_text="Orden de importancia")

    # Timestamps
    fecha_creacion = models.DateTimeField(default=timezone.now, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-prioridad', 'nombre']
        indexes = [
            models.Index(fields=['sofascore_id']),
            models.Index(fields=['pais', 'tipo']),
        ]

    def __str__(self):
        return self.nombre


class Temporada(models.Model):
    sofascore_id = models.IntegerField(unique=True)
    liga = models.ForeignKey(Liga, on_delete=models.CASCADE, related_name='temporadas')
    nombre = models.CharField(max_length=50, help_text="Ej: 2024/25")
    year = models.CharField(max_length=10, blank=True)
    año_inicio = models.IntegerField()
    año_fin = models.IntegerField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    # Timestamps
    fecha_creacion = models.DateTimeField(default=timezone.now, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-año_inicio', '-activa']
        # Removemos unique_together para permitir mismo año en diferentes ligas
        # unique_together = ['liga', 'año_inicio']
        indexes = [
            models.Index(fields=['sofascore_id']),
            models.Index(fields=['liga', 'activa']),
            models.Index(fields=['liga', 'año_inicio']),
        ]

    def __str__(self):
        return f"{self.liga.nombre} - {self.nombre}"


class Equipo(models.Model):
    sofascore_id = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=200)
    nombre_corto = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    pais = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, related_name='equipos')
    ciudad = models.CharField(max_length=100, blank=True)
    estadio = models.CharField(max_length=200, blank=True)
    capacidad_estadio = models.IntegerField(null=True, blank=True)
    fundacion = models.IntegerField(null=True, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)

    # Manager y entrenador
    manager = models.CharField(max_length=200, blank=True, verbose_name="Director Técnico")

    # Colores del equipo (JSON con primary, secondary, text)
    colores = models.JSONField(default=dict, blank=True)

    # Información adicional
    tipo = models.CharField(max_length=50, blank=True, help_text="national, club")
    genero = models.CharField(max_length=10, default='M', choices=[('M', 'Masculino'), ('F', 'Femenino')])

    # Redes sociales y web
    sitio_web = models.URLField(max_length=500, blank=True)

    # Timestamps
    fecha_creacion = models.DateTimeField(default=timezone.now, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['sofascore_id']),
            models.Index(fields=['pais']),
        ]

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
    slug = models.SlugField(max_length=200, blank=True)
    equipo = models.ForeignKey(Equipo, on_delete=models.SET_NULL, null=True, blank=True, related_name='jugadores')

    # Información personal
    fecha_nacimiento = models.DateField(null=True, blank=True)
    fecha_nacimiento_timestamp = models.BigIntegerField(null=True, blank=True)
    pais_nacimiento = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='jugadores_nacidos')
    ciudad_nacimiento = models.CharField(max_length=100, blank=True)
    nacionalidad = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='jugadores_nacionalidad')

    # Información deportiva
    posicion = models.CharField(max_length=3, choices=POSICION_CHOICES)
    posicion_detallada = models.CharField(max_length=50, blank=True,
                                          help_text="Ej: Central defender, Attacking midfielder")
    numero_camiseta = models.IntegerField(null=True, blank=True)
    altura = models.FloatField(null=True, blank=True, help_text="Altura en cm")
    peso = models.FloatField(null=True, blank=True, help_text="Peso en kg")
    pie_preferido = models.CharField(max_length=20, choices=PIE_CHOICES, blank=True)

    # URLs
    foto_url = models.URLField(max_length=500, blank=True)

    # Información de mercado
    valor_mercado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    moneda_valor_mercado = models.CharField(max_length=3, default='EUR')

    # Contrato
    fecha_fin_contrato = models.DateField(null=True, blank=True)

    # Estado
    retirado = models.BooleanField(default=False)

    # Timestamps
    fecha_creacion = models.DateTimeField(default=timezone.now, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = "Jugadores"
        indexes = [
            models.Index(fields=['sofascore_id']),
            models.Index(fields=['equipo', 'posicion']),
        ]

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
        ('interrupted', 'Interrumpido'),
        ('suspended', 'Suspendido'),
    ]

    sofascore_id = models.IntegerField(unique=True)
    custom_id = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=300, blank=True)

    # Relaciones
    liga = models.ForeignKey(Liga, on_delete=models.CASCADE, related_name='partidos')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE, related_name='partidos')
    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local')
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visitante')

    # Fecha y hora
    fecha_hora = models.DateTimeField()
    fecha_hora_timestamp = models.BigIntegerField(null=True, blank=True)
    jornada = models.IntegerField(null=True, blank=True)
    ronda = models.CharField(max_length=100, blank=True)

    # Marcadores - Tiempo regular
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visitante = models.IntegerField(null=True, blank=True)
    goles_local_ht = models.IntegerField(null=True, blank=True, help_text="Medio tiempo")
    goles_visitante_ht = models.IntegerField(null=True, blank=True, help_text="Medio tiempo")

    # Marcadores - Tiempo extra y penales
    goles_local_et = models.IntegerField(null=True, blank=True, help_text="Tiempo extra")
    goles_visitante_et = models.IntegerField(null=True, blank=True, help_text="Tiempo extra")
    penales_local = models.IntegerField(null=True, blank=True)
    penales_visitante = models.IntegerField(null=True, blank=True)

    # Marcadores agregados (para eliminatorias)
    goles_local_agregado = models.IntegerField(null=True, blank=True)
    goles_visitante_agregado = models.IntegerField(null=True, blank=True)

    # Estado del partido
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='notstarted')
    estado_codigo = models.IntegerField(null=True, blank=True)
    estado_descripcion = models.CharField(max_length=100, blank=True)
    minuto_actual = models.IntegerField(null=True, blank=True)

    # Información adicional
    estadio = models.CharField(max_length=200, blank=True)
    arbitro = models.CharField(max_length=200, blank=True)
    arbitro_pais = models.ForeignKey(Pais, on_delete=models.SET_NULL, null=True, blank=True, related_name='arbitrajes')
    asistencia = models.IntegerField(null=True, blank=True)

    # Clima (JSON con temperatura, condición, etc)
    clima = models.JSONField(default=dict, blank=True)

    # Información del partido
    tiene_lineups = models.BooleanField(default=False)
    tiene_estadisticas = models.BooleanField(default=False)
    tiene_incidentes = models.BooleanField(default=False)

    # Ganador (útil para copas)
    ganador = models.ForeignKey(Equipo, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='partidos_ganados')

    # Timestamps
    fecha_creacion = models.DateTimeField(default=timezone.now, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name_plural = "Partidos"
        indexes = [
            models.Index(fields=['sofascore_id']),
            models.Index(fields=['liga', 'temporada', 'fecha_hora']),
            models.Index(fields=['estado', 'fecha_hora']),
            models.Index(fields=['equipo_local', 'fecha_hora']),
            models.Index(fields=['equipo_visitante', 'fecha_hora']),
        ]

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
    tiros_fuera_local = models.IntegerField(default=0)
    tiros_bloqueados_local = models.IntegerField(default=0)
    corners_local = models.IntegerField(default=0)
    faltas_local = models.IntegerField(default=0)
    tarjetas_amarillas_local = models.IntegerField(default=0)
    tarjetas_rojas_local = models.IntegerField(default=0)
    fueras_juego_local = models.IntegerField(default=0)
    saques_banda_local = models.IntegerField(default=0)
    saques_puerta_local = models.IntegerField(default=0)

    # Estadísticas visitante
    posesion_visitante = models.FloatField(null=True, blank=True)
    tiros_visitante = models.IntegerField(default=0)
    tiros_puerta_visitante = models.IntegerField(default=0)
    tiros_fuera_visitante = models.IntegerField(default=0)
    tiros_bloqueados_visitante = models.IntegerField(default=0)
    corners_visitante = models.IntegerField(default=0)
    faltas_visitante = models.IntegerField(default=0)
    tarjetas_amarillas_visitante = models.IntegerField(default=0)
    tarjetas_rojas_visitante = models.IntegerField(default=0)
    fueras_juego_visitante = models.IntegerField(default=0)
    saques_banda_visitante = models.IntegerField(default=0)
    saques_puerta_visitante = models.IntegerField(default=0)

    # Estadísticas avanzadas (JSON para flexibilidad)
    estadisticas_adicionales = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Estadísticas de partido"
        unique_together = ['partido', 'periodo']
        indexes = [
            models.Index(fields=['partido', 'periodo']),
        ]

    def __str__(self):
        return f"Estadísticas {self.partido} - {self.periodo}"


class EventoPartido(models.Model):
    TIPO_CHOICES = [
        ('goal', 'Gol'),
        ('yellow_card', 'Tarjeta amarilla'),
        ('red_card', 'Tarjeta roja'),
        ('yellow_red_card', 'Segunda amarilla'),
        ('substitution', 'Sustitución'),
        ('penalty', 'Penalti'),
        ('penalty_missed', 'Penalti fallado'),
        ('own_goal', 'Autogol'),
        ('var', 'VAR'),
        ('injury', 'Lesión'),
        ('period', 'Cambio de período'),
    ]

    sofascore_id = models.BigIntegerField(null=True, blank=True)
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='eventos')
    jugador = models.ForeignKey(Jugador, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    jugador_relacionado = models.ForeignKey(Jugador, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='eventos_relacionados',
                                            help_text="Para asistencias o sustituciones")

    minuto = models.IntegerField()
    minuto_adicional = models.IntegerField(null=True, blank=True)
    segundo = models.IntegerField(null=True, blank=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    descripcion = models.TextField(blank=True)
    texto_incidente = models.CharField(max_length=200, blank=True)
    es_local = models.BooleanField(default=True)

    # Información adicional (JSON)
    datos_adicionales = models.JSONField(default=dict, blank=True)

    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['minuto', 'segundo']
        verbose_name_plural = "Eventos de partido"
        indexes = [
            models.Index(fields=['partido', 'minuto']),
            models.Index(fields=['jugador', 'tipo']),
        ]

    def __str__(self):
        tiempo = f"{self.minuto}'" if not self.minuto_adicional else f"{self.minuto}+{self.minuto_adicional}'"
        return f"{self.get_tipo_display()} - {tiempo}"


class Alineacion(models.Model):
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='alineaciones')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE)
    es_local = models.BooleanField(default=True)
    es_titular = models.BooleanField(default=True)

    # Posición
    posicion = models.CharField(max_length=50, blank=True)
    numero_camiseta = models.IntegerField(null=True, blank=True)
    formacion_posicion = models.CharField(max_length=10, blank=True, help_text="Ej: GK, LB, CM")
    posicion_x = models.FloatField(null=True, blank=True)
    posicion_y = models.FloatField(null=True, blank=True)

    # Sustitución
    sustituido = models.BooleanField(default=False)
    minuto_entrada = models.IntegerField(null=True, blank=True)
    minuto_salida = models.IntegerField(null=True, blank=True)

    # Estadísticas del jugador en el partido
    rating = models.FloatField(null=True, blank=True)
    minutos_jugados = models.IntegerField(default=0)
    goles = models.IntegerField(default=0)
    asistencias = models.IntegerField(default=0)
    tarjetas_amarillas = models.IntegerField(default=0)
    tarjetas_rojas = models.IntegerField(default=0)

    # Estadísticas detalladas (JSON para flexibilidad)
    estadisticas_detalladas = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Alineaciones"
        unique_together = ['partido', 'jugador']
        indexes = [
            models.Index(fields=['partido', 'es_titular']),
            models.Index(fields=['jugador', 'partido']),
        ]

    def __str__(self):
        titular = "Titular" if self.es_titular else "Suplente"
        return f"{self.jugador.nombre} - {titular}"


class EstadisticaJugador(models.Model):
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='estadisticas')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    liga = models.ForeignKey(Liga, on_delete=models.CASCADE, null=True, blank=True)

    # Estadísticas generales
    partidos_jugados = models.IntegerField(default=0)
    partidos_titular = models.IntegerField(default=0)
    minutos_jugados = models.IntegerField(default=0)
    goles = models.IntegerField(default=0)
    asistencias = models.IntegerField(default=0)
    tarjetas_amarillas = models.IntegerField(default=0)
    tarjetas_rojas = models.IntegerField(default=0)
    rating_promedio = models.FloatField(null=True, blank=True)

    # Estadísticas detalladas de tiros
    tiros_totales = models.IntegerField(default=0)
    tiros_puerta = models.IntegerField(default=0)
    precision_tiros = models.FloatField(null=True, blank=True)
    goles_esperados = models.FloatField(null=True, blank=True, verbose_name="xG")

    # Pases
    pases_completados = models.IntegerField(default=0)
    pases_intentados = models.IntegerField(default=0)
    precision_pases = models.FloatField(null=True, blank=True)
    pases_clave = models.IntegerField(default=0)
    pases_largos = models.IntegerField(default=0)
    centros = models.IntegerField(default=0)

    # Duelos y defensiva
    duelos_ganados = models.IntegerField(default=0)
    duelos_totales = models.IntegerField(default=0)
    duelos_aereos_ganados = models.IntegerField(default=0)
    duelos_aereos_totales = models.IntegerField(default=0)
    tacleadas = models.IntegerField(default=0)
    intercepciones = models.IntegerField(default=0)
    despejes = models.IntegerField(default=0)

    # Porteros
    atajadas = models.IntegerField(default=0)
    goles_recibidos = models.IntegerField(default=0)
    porteria_cero = models.IntegerField(default=0, verbose_name="Clean sheets")

    # Disciplina
    faltas_cometidas = models.IntegerField(default=0)
    faltas_recibidas = models.IntegerField(default=0)

    # Estadísticas adicionales (JSON)
    estadisticas_adicionales = models.JSONField(default=dict, blank=True)

    # Timestamps
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Estadísticas de jugador"
        unique_together = ['jugador', 'temporada', 'liga']
        indexes = [
            models.Index(fields=['jugador', 'temporada']),
            models.Index(fields=['temporada', 'goles']),
        ]

    def __str__(self):
        return f"{self.jugador.nombre} - {self.temporada}"

    @property
    def goles_por_partido(self):
        if self.partidos_jugados > 0:
            return round(self.goles / self.partidos_jugados, 2)
        return 0

    @property
    def precision_pases_porcentaje(self):
        if self.pases_intentados > 0:
            return round((self.pases_completados / self.pases_intentados) * 100, 1)
        return 0