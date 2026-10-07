"""Aislamiento del panel: cada vendedor ve y edita solo lo de sus tiendas."""
from django import forms
from django.contrib import admin

from .services import tiendas_de, ve_todas


def tiendas_del_panel(request):
    """Tiendas del usuario que esta en el panel; se consulta una sola vez por peticion."""
    if not hasattr(request, '_tiendas_del_panel'):
        request._tiendas_del_panel = list(tiendas_de(request.user))
    return request._tiendas_del_panel


def maneja_varias_tiendas(request):
    return ve_todas(request.user) or len(tiendas_del_panel(request)) > 1


def preparar_campo_tienda(campo, request, fija=False):
    """Ajusta el campo `tienda` de un formulario del panel.

    Solo ofrece las tiendas del usuario; quien tiene una sola no ve el campo. Con `fija` el valor
    no se puede cambiar. El campo sigue en el formulario (oculto o deshabilitado) para que se
    validen las restricciones de unicidad por tienda.
    """
    tiendas = tiendas_del_panel(request)
    campo.queryset = campo.queryset.filter(pk__in=[tienda.pk for tienda in tiendas])
    campo.empty_label = None if len(tiendas) == 1 else campo.empty_label
    campo.disabled = fija
    if len(tiendas) == 1 and not fija:
        campo.initial = tiendas[0].pk
    if not maneja_varias_tiendas(request):
        campo.widget = forms.HiddenInput()
    else:
        # Las tiendas se administran en su propia pantalla, no desde este desplegable.
        for permiso in ('can_add_related', 'can_change_related', 'can_delete_related', 'can_view_related'):
            if hasattr(campo.widget, permiso):
                setattr(campo.widget, permiso, False)


class AdminDeTienda:
    """ModelAdmin de un modelo con clave foranea `tienda`. Va antes de ModelAdmin en la herencia.

    - Las listas, el detalle, las acciones y la exportacion salen de `get_queryset`, que deja
      fuera lo de otras tiendas.
    - Al crear, la tienda es una de las del usuario; despues ya no cambia.
    - Quien maneja varias tiendas ve la columna y el filtro `tienda`.
    """

    def get_queryset(self, request):
        consulta = super().get_queryset(request)
        if ve_todas(request.user):
            return consulta
        return consulta.filter(tienda__in=tiendas_del_panel(request))

    def get_form(self, request, obj=None, **kwargs):
        formulario = super().get_form(request, obj, **kwargs)
        campo = formulario.base_fields.get('tienda')
        if campo is not None:
            preparar_campo_tienda(campo, request, fija=obj is not None)
        return formulario

    def get_list_display(self, request):
        columnas = list(super().get_list_display(request))
        if maneja_varias_tiendas(request) and 'tienda' not in columnas:
            columnas.append('tienda')
        return columnas

    def get_list_filter(self, request):
        filtros = list(super().get_list_filter(request))
        if maneja_varias_tiendas(request):
            filtros.insert(0, ('tienda', admin.RelatedOnlyFieldListFilter))
        return filtros

    def get_list_select_related(self, request):
        relacionados = super().get_list_select_related(request)
        if relacionados is True or not maneja_varias_tiendas(request):
            return relacionados
        return [*(relacionados or []), 'tienda']
