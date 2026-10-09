"""Ayuda para las migraciones de datos de las otras apps al pasar a varias tiendas."""


def asignar_a_la_tienda_principal(app, *modelos):
    """Operacion RunPython: lo que aun no tiene tienda pasa a la primera (la que ya existia).

    Usa los modelos historicos de `apps`, asi que sirve dentro de cualquier migracion.
    """
    def operacion(apps, schema_editor):
        principal = apps.get_model('tiendas', 'Tienda').objects.order_by('pk').first()
        if principal is None:
            return
        for modelo in modelos:
            apps.get_model(app, modelo).objects.filter(tienda__isnull=True).update(tienda=principal)
    return operacion


def con_codigo_de_pais(numero):
    """WhatsApp solo con digitos; al numero dominicano de 10 digitos le antepone el 1 (wa.me lo exige)."""
    digitos = ''.join(c for c in (numero or '') if c.isdigit())
    if len(digitos) == 10 and digitos.startswith(('809', '829', '849')):
        digitos = '1' + digitos
    return digitos


def poner_codigo_de_pais(app, modelo):
    """Operacion RunPython: corrige los WhatsApp guardados sin codigo de pais."""
    def operacion(apps, schema_editor):
        for fila in apps.get_model(app, modelo).objects.exclude(whatsapp=''):
            corregido = con_codigo_de_pais(fila.whatsapp)
            if corregido != fila.whatsapp:
                fila.whatsapp = corregido
                fila.save(update_fields=['whatsapp'])
    return operacion
