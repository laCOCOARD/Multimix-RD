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
