bl_info = {
    "name": "Batch Asset Placer",
    "author": "Andrey Pestryakov (3D Vopros) - https://vk.com/3dvopros",
    "version": (1, 0),
    "blender": (4, 5, 0),
    "location": "Asset Browser > Header > Add Selected Assets",
    "description": "Adds all selected assets from Asset Browser to the scene at the 3D cursor position",
    "category": "Import-Export",
}

import bpy
import os
from mathutils import Vector


class ASSET_OT_AddSelectedAssets(bpy.types.Operator):
    """Add selected assets from external .blend files or current file"""
    bl_idname = "asset.add_selected_assets"
    bl_label = "Add Selected Assets"
    bl_options = {'REGISTER', 'UNDO'}
    
    spacing: bpy.props.FloatProperty(
        name="Spacing",
        description="Distance between objects",
        default=0.5,
        min=0.01,
        max=100.0,
        step=1,
        precision=2
    )

    def clear_asset_marker(self, obj):
        """Remove asset marker from an object using direct API (no bpy.ops)"""
        if not obj:
            return
        
        # Правильный способ: сначала проверить, является ли объект ассетом
        # и только потом очищать
        try:
            # Пытаемся очистить через API, если объект помечен как ассет
            if hasattr(obj, 'asset_data') and obj.asset_data is not None:
                # Вместо присваивания None, используем специальный метод
                # Но simpler approach - просто удаляем свойство
                if hasattr(obj, 'asset_mark_clear'):
                    obj.asset_mark_clear()
                print(f"  Cleared asset marker from object: {obj.name}")
        except Exception as e:
            print(f"  Warning: Could not clear asset from {obj.name}: {e}")
        
        # Очистка пользовательских свойств (это безопасно всегда)
        if hasattr(obj, 'keys'):
            asset_props = [k for k in obj.keys() if 'asset' in k.lower()]
            for prop in asset_props:
                try:
                    del obj[prop]
                    print(f"  Cleared asset property from object: {obj.name}")
                except:
                    pass

    def clear_asset_marker_safe(self, obj):
        """Безопасная очистка маркера ассета - работает для любых объектов"""
        if not obj:
            return
        
        # Пробуем метод clear, если он существует
        if hasattr(obj, 'asset_mark_clear'):
            try:
                obj.asset_mark_clear()
                print(f"  Cleared asset marker from: {obj.name}")
                return
            except:
                pass
        
        # Если объект не помечен как ассет, просто чистим свойства
        if hasattr(obj, 'keys'):
            asset_props = [k for k in obj.keys() if 'asset' in k.lower() or k == 'is_asset']
            for prop in asset_props:
                try:
                    del obj[prop]
                    print(f"  Cleared asset property: {prop} from {obj.name}")
                except:
                    pass

    def clear_material_asset_markers(self, obj):
        """Remove asset markers from all materials"""
        if not hasattr(obj, 'data'):
            return
        if not hasattr(obj.data, 'materials'):
            return
        
        for material in obj.data.materials:
            if not material:
                continue
            
            try:
                # Безопасная очистка для материалов
                if hasattr(material, 'asset_mark_clear'):
                    material.asset_mark_clear()
                    print(f"  Cleared asset marker from material: {material.name}")
                
                if hasattr(material, 'keys'):
                    asset_props = [k for k in material.keys() if 'asset' in k.lower()]
                    for prop in asset_props:
                        try:
                            del material[prop]
                            print(f"  Cleared asset property from material: {material.name}")
                        except:
                            pass
                
                material.update_tag()
                
            except Exception as e:
                print(f"  Could not clear material {material.name}: {e}")

    def deduplicate_materials_batch(self, objects):
        """Массовая замена дубликатов материалов в группе объектов"""
        # Собираем информацию о заменах
        replacements = []  # (obj, slot_index, duplicate_material, original_material)
        duplicates_to_remove = set()
        
        for obj in objects:
            if not hasattr(obj, 'data'):
                continue
            if not hasattr(obj.data, 'materials'):
                continue
            if obj.type != 'MESH':
                continue
            
            for slot_index, material in enumerate(obj.data.materials):
                if not material:
                    continue
                
                material_name = material.name
                
                # Проверяем наличие суффикса .001, .002 и т.д.
                if '.' in material_name:
                    parts = material_name.rsplit('.', 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        base_name = parts[0]
                        
                        # Ищем оригинальный материал в bpy.data.materials
                        if base_name in bpy.data.materials:
                            original_material = bpy.data.materials[base_name]
                            
                            # Если нашли оригинал и это не тот же самый материал
                            if original_material != material:
                                replacements.append((obj, slot_index, material, original_material))
                                duplicates_to_remove.add(material)
        
        # Применяем замены
        for obj, slot_index, dup_mat, orig_mat in replacements:
            try:
                obj.data.materials[slot_index] = orig_mat
                print(f"  Replaced '{dup_mat.name}' with '{orig_mat.name}' in {obj.name}")
            except Exception as e:
                print(f"  Error replacing material in {obj.name}: {e}")
        
        # Удаляем дубликаты материалов, которые больше не используются
        for dup_mat in duplicates_to_remove:
            try:
                # Проверяем, используется ли этот материал где-то еще
                is_used = False
                
                # Проверяем все объекты
                for obj in bpy.data.objects:
                    if hasattr(obj, 'data') and hasattr(obj.data, 'materials'):
                        if obj.data.materials:
                            for mat in obj.data.materials:
                                if mat == dup_mat:
                                    is_used = True
                                    break
                    if is_used:
                        break
                
                # Проверяем, не используется ли в других местах (например, в нодах)
                if not is_used and dup_mat.users == 0:
                    # Сначала очищаем маркеры ассета
                    if hasattr(dup_mat, 'asset_mark_clear'):
                        dup_mat.asset_mark_clear()
                    
                    bpy.data.materials.remove(dup_mat)
                    print(f"  Removed duplicate material: {dup_mat.name}")
                else:
                    print(f"  Material {dup_mat.name} still in use, keeping it")
                    
            except Exception as e:
                print(f"  Could not remove {dup_mat.name}: {e}")

    def duplicate_and_clean(self, obj, is_external=True):
        """Duplicate object, optionally remove original with asset marker"""
        if not obj:
            return None
        
        # Сохраняем имена оригинальных материалов
        original_material_names = []
        if obj.type == 'MESH' and obj.data and obj.data.materials:
            for mat in obj.data.materials:
                if mat:
                    original_material_names.append(mat.name)
                else:
                    original_material_names.append(None)
        
        duplicated = obj.copy()
        
        if obj.type == 'MESH' and obj.data:
            duplicated.data = obj.data.copy()
        
        bpy.context.collection.objects.link(duplicated)
        
        # Восстанавливаем ссылки на оригинальные материалы (если они были)
        if original_material_names and duplicated.type == 'MESH' and duplicated.data:
            # Очищаем существующие материалы
            duplicated.data.materials.clear()
            # Добавляем материалы по именам (это предотвратит создание дубликатов)
            for mat_name in original_material_names:
                if mat_name and mat_name in bpy.data.materials:
                    duplicated.data.materials.append(bpy.data.materials[mat_name])
                else:
                    duplicated.data.materials.append(None)
        
        if is_external:
            bpy.data.objects.remove(obj, do_unlink=True)
        
        return duplicated

    def append_from_blend(self, blend_file, data_type, data_name, link=False):
        """Add or link data from .blend file (external)"""
        try:
            if not os.path.exists(blend_file):
                self.report({'WARNING'}, f"File not found: {blend_file}")
                return None
            
            with bpy.data.libraries.load(blend_file, link=link) as (data_from, data_to):
                if data_type == "Object" and data_name in data_from.objects:
                    data_to.objects = [data_name]
                elif data_type == "Collection" and data_name in data_from.collections:
                    data_to.collections = [data_name]
                else:
                    self.report({'WARNING'}, f"{data_type} '{data_name}' not found in {blend_file}")
                    return None

            if data_type == "Object":
                for obj in data_to.objects:
                    if obj:
                        bpy.context.collection.objects.link(obj)
                        return self.duplicate_and_clean(obj, is_external=True)
            elif data_type == "Collection":
                for col in data_to.collections:
                    if col:
                        bpy.context.scene.collection.children.link(col)
                        if col.objects:
                            return self.duplicate_and_clean(col.objects[0], is_external=True)
                        return None
        except Exception as e:
            self.report({'WARNING'}, f"Error loading from {blend_file}: {str(e)}")
            return None
        return None

    def copy_local_asset(self, asset):
        """Copy asset from current file (keep original asset)"""
        original_obj = None
        
        if hasattr(asset, 'local_id') and asset.local_id is not None:
            original_obj = asset.local_id
        else:
            asset_name = asset.name
            if asset_name in bpy.data.objects:
                original_obj = bpy.data.objects[asset_name]
        
        if original_obj:
            # Для локальных ассетов не удаляем оригинал и не очищаем маркеры
            # Просто создаем копию объекта
            duplicated = original_obj.copy()
            
            if original_obj.type == 'MESH' and original_obj.data:
                duplicated.data = original_obj.data.copy()
            
            bpy.context.collection.objects.link(duplicated)
            
            # Копируем материалы без изменений
            if original_obj.type == 'MESH' and original_obj.data and original_obj.data.materials:
                for i, mat in enumerate(original_obj.data.materials):
                    if i < len(duplicated.data.materials):
                        duplicated.data.materials[i] = mat
            
            return duplicated
        
        self.report({'WARNING'}, f"Failed to copy local asset '{asset.name}'")
        return None

    def get_asset_info(self, asset):
        """Get asset info: type, name, file path"""
        if hasattr(asset, 'local_id') and asset.local_id is not None:
            return 'LOCAL', asset.name, None
        
        if hasattr(asset, 'full_path') and asset.full_path:
            full_path = asset.full_path
            
            if '.blend' in full_path:
                try:
                    blend_pos = full_path.find('.blend')
                    if blend_pos != -1:
                        blend_path = full_path[:blend_pos + 6]
                        
                        remaining = full_path[blend_pos + 6:].strip(os.sep)
                        parts = remaining.split(os.sep)
                        
                        if len(parts) >= 2:
                            data_type = parts[0]
                            asset_name = parts[1]
                        else:
                            data_type = "Object"
                            asset_name = asset.name
                        
                        return data_type, asset_name, blend_path
                except Exception as e:
                    self.report({'WARNING'}, f"Error parsing path {full_path}: {str(e)}")
        
        return None, None, None

    def calculate_positions(self, num_assets, spacing):
        """Calculate positions for assets in a grid layout"""
        if num_assets == 0:
            return []
        
        cursor_location = bpy.context.scene.cursor.location.copy()
        positions = []
        
        row_size = 5
        
        for i in range(num_assets):
            row = i // row_size
            col = i % row_size
            x = cursor_location.x + (col * spacing)
            y = cursor_location.y + (row * spacing)
            z = cursor_location.z
            
            positions.append(Vector((x, y, z)))
        
        return positions

    def clear_all_asset_markers(self, obj):
        """Полностью очищает все маркеры ассета у объекта и его материалов"""
        self.clear_asset_marker_safe(obj)
        self.clear_material_asset_markers(obj)

    def execute(self, context):
        selected_assets = list(context.selected_assets)
        num_assets = len(selected_assets)
        
        if num_assets == 0:
            self.report({'WARNING'}, "No assets selected")
            return {'CANCELLED'}
        
        loaded_objects = []
        # Запоминаем, какие объекты были добавлены из внешних файлов
        external_objects = []
        
        for asset in selected_assets:
            try:
                data_type, asset_id, blend_path = self.get_asset_info(asset)
                
                if data_type == 'LOCAL':
                    obj = self.copy_local_asset(asset)
                    if obj:
                        loaded_objects.append(obj)
                        self.report({'INFO'}, f"Added: {obj.name} (local)")
                elif blend_path and asset_id:
                    obj = self.append_from_blend(blend_path, data_type, asset_id, link=False)
                    if obj:
                        loaded_objects.append(obj)
                        external_objects.append(obj)  # Запоминаем внешние объекты
                        self.report({'INFO'}, f"Added: {obj.name} (external)")
                else:
                    self.report({'WARNING'}, f"Unknown asset type: {asset.name}")
            except Exception as e:
                self.report({'WARNING'}, f"Error adding asset '{asset.name}': {str(e)}")
        
        if not loaded_objects:
            self.report({'WARNING'}, "Failed to load any assets")
            return {'CANCELLED'}
        
        if hasattr(context.scene, 'asset_spacing'):
            final_spacing = context.scene.asset_spacing
        else:
            final_spacing = self.spacing
        
        positions = self.calculate_positions(len(loaded_objects), final_spacing)
        
        print(f"Loaded {len(loaded_objects)} objects, {len(positions)} positions")
        for i, (obj, pos) in enumerate(zip(loaded_objects, positions)):
            obj.location = pos
            print(f"  {i+1}. {obj.name} -> {pos}")
        
        print("\n=== Removing duplicate materials ===")
        # Дедупликация материалов (для всех добавленных объектов)
        self.deduplicate_materials_batch(loaded_objects)
        
        # Очищаем маркеры ассетов ТОЛЬКО для внешних объектов
        if external_objects:
            print("\n=== Clearing asset markers for external objects only ===")
            for obj in external_objects:
                self.clear_all_asset_markers(obj)
        else:
            print("\n=== No external objects, skipping asset marker clearing ===")
        
        for obj in loaded_objects:
            obj.select_set(True)
        
        if loaded_objects:
            context.view_layer.objects.active = loaded_objects[0]
        
        context.view_layer.update()
        
        self.report({'INFO'}, f"Done! Added {len(loaded_objects)} assets (spacing: {final_spacing}, external: {len(external_objects)})")
        return {'FINISHED'}


def display_button(self, context):
    """Add button to Asset Browser menu"""
    layout = self.layout
    layout.separator()
    
    row = layout.row(align=True)
    row.operator(ASSET_OT_AddSelectedAssets.bl_idname)
    row.prop(context.scene, "asset_spacing", text="")


def register_scene_properties():
    bpy.types.Scene.asset_spacing = bpy.props.FloatProperty(
        name="Spacing",
        description="Distance between objects",
        default=0.5,
        min=0.01,
        max=100.0,
        step=1,
        precision=2
    )


def unregister_scene_properties():
    if hasattr(bpy.types.Scene, 'asset_spacing'):
        del bpy.types.Scene.asset_spacing


def register():
    register_scene_properties()
    bpy.utils.register_class(ASSET_OT_AddSelectedAssets)
    bpy.types.ASSETBROWSER_MT_editor_menus.append(display_button)


def unregister():
    bpy.types.ASSETBROWSER_MT_editor_menus.remove(display_button)
    bpy.utils.unregister_class(ASSET_OT_AddSelectedAssets)
    unregister_scene_properties()


if __name__ == "__main__":
    register()