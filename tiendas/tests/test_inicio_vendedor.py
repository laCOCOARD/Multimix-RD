"""Inicio del panel para el dueño de la tienda (2026-10-28): que hacer ahora, primeros pasos, menu agrupado y
titulos simples. Cada vendedor solo cuenta lo de su tienda."""
from django.urls import reverse

from opiniones.models import Pregunta
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import pedido_de_prueba

from .test_panel import PanelDeVendedores


class InicioDelVendedorTests(PanelDeVendedores):
    def tareas(self):
        return {t['texto']: t['cantidad'] for t in self.client.get(reverse('admin:index')).context['tareas']}

    def test_para_hacer_ahora_solo_cuenta_lo_de_su_tienda(self):
        # El pedido de la fixture esta pendiente y sin transferencia avisada: no le toca hacer nada todavia.
        self.assertEqual(self.tareas(), {})
        self.assertContains(self.client.get(reverse('admin:index')), 'Todo al día')
        Pedido.objects.filter(pk=self.pedido_propio.pk).update(transferencia_realizada=True)
        cambiar_estado(self.pedido_ajeno, Pedido.Estado.PAGADO)  # de la otra tienda: no cuenta
        self.assertEqual(self.tareas(), {'transferencia por confirmar': 1})
        cambiar_estado(self.pedido_propio, Pedido.Estado.PAGADO)
        self.assertEqual(self.tareas(), {'pedido pagado por preparar': 1})
        cambiar_estado(self.pedido_propio, Pedido.Estado.PREPARANDO)
        self.assertEqual(self.tareas(), {'pedido en preparación': 1})
        cambiar_estado(self.pedido_propio, Pedido.Estado.LISTO)
        self.assertEqual(self.tareas(), {'pedido por entregar': 1})
        self.lampara.tienda.permitir_contra_entrega = True
        self.lampara.tienda.save()
        pedido_de_prueba(self.lampara, 1, metodo_pago=Pedido.Pago.CONTRA_ENTREGA, metodo_entrega=Pedido.Entrega.ENVIO,
                         zona=self.zona_propia, direccion='Calle 1')
        Pregunta.objects.create(tienda=self.propia, producto=self.lampara, usuario=self.vendedor, texto='¿Tienen azul?')
        Pregunta.objects.create(tienda=self.ajena, producto=self.pesas, usuario=self.vendedor, texto='¿Y de 10 kg?')
        self.assertEqual(self.tareas(), {
            'pedido contra entrega': 1, 'pedido por entregar': 1, 'pregunta sin responder': 1,
        })

    def test_cada_tarea_lleva_a_su_lista_filtrada(self):
        Pedido.objects.filter(pk=self.pedido_propio.pk).update(transferencia_realizada=True)
        tarea = self.client.get(reverse('admin:index')).context['tareas'][0]
        lista = self.client.get(tarea['url'])
        self.assertEqual(list(lista.context['cl'].result_list), [self.pedido_propio])
        cambiar_estado(self.pedido_propio, Pedido.Estado.PAGADO)
        cambiar_estado(self.pedido_propio, Pedido.Estado.PREPARANDO)
        cambiar_estado(self.pedido_propio, Pedido.Estado.LISTO)
        tarea = self.client.get(reverse('admin:index')).context['tareas'][0]
        self.assertEqual(list(self.client.get(tarea['url']).context['cl'].result_list), [self.pedido_propio])

    def test_primeros_pasos_mientras_falte_algo(self):
        # La tienda de prueba tiene cuenta y zona, pero no WhatsApp y su producto no tiene foto.
        respuesta = self.client.get(reverse('admin:index'))
        [(tienda, pasos)] = respuesta.context['primeros_pasos']
        self.assertEqual([p['texto'] for p in pasos if not p['hecho']],
                         ['Pon tu número de WhatsApp', 'Publica tu primer producto con foto'])
        self.assertContains(respuesta, 'Deja lista tu tienda')
        self.propia.cuentas.update(activa=False)
        pasos = dict(self.client.get(reverse('admin:index')).context['primeros_pasos'])[self.propia]
        self.assertIn('Agrega una cuenta de banco para recibir transferencias', [p['texto'] for p in pasos if not p['hecho']])

    def test_menu_agrupado_y_titulos_simples(self):
        respuesta = self.client.get(reverse('admin:index'))
        grupos = {g['name']: [m['name'] for m in g['models']] for g in respuesta.context['app_list']}
        self.assertEqual(list(grupos)[:2], ['Pedidos', 'Productos'])
        self.assertIn('Mis productos', grupos['Productos'])
        self.assertIn('Datos de la tienda', grupos['Mi tienda'])
        self.assertNotContains(respuesta, 'Acciones recientes')
        self.assertContains(self.client.get(reverse('admin:catalogo_producto_changelist')), '<h1>Productos</h1>')
        self.assertContains(self.client.get(reverse('admin:catalogo_producto_add')), '<h1>Agregar producto</h1>')
        self.assertContains(self.client.get(reverse('admin:catalogo_producto_change', args=[self.lampara.pk])),
                            '<h1>Editar producto</h1>')

    def test_el_administrador_conserva_su_inicio(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin:index'))
        self.assertNotIn('tareas', respuesta.context)
        self.assertContains(respuesta, 'Resumen del sitio')
        self.assertNotIn('Mi tienda', [g['name'] for g in respuesta.context['app_list']])
