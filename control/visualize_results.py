#!/usr/bin/env python3
"""
Скрипт для визуализации результатов тестирования.
Создает графики для сравнения результатов между разными типами хранилищ.
"""
import json
import sys
import os
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
matplotlib.use('Agg')  # Для работы без GUI

# Цветовая схема для типов хранилищ
STORAGE_COLORS = {
    'local': '#1f77b4',  # Синий для локального хранилища
    'iscsi': '#ff7f0e',  # Оранжевый для iSCSI
    'default': '#2ca02c'  # Зеленый для неопознанных типов
}

def load_aggregated_data(json_file):
    """Загружает агрегированные данные из JSON"""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки {json_file}: {str(e)}")
        return None

def get_storage_type(label):
    """Извлекает тип хранилища из метки"""
    label_lower = label.lower()
    if 'local' in label_lower:
        return 'local'
    elif 'iscsi' in label_lower:
        return 'iscsi'
    else:
        return 'default'

def get_color_for_storage(storage_type):
    """Возвращает цвет для типа хранилища"""
    return STORAGE_COLORS.get(storage_type, STORAGE_COLORS['default'])

def plot_fio_comparison(datasets, output_dir):
    """Создает графики сравнения FIO тестов с цветовой схемой"""
    # Получаем все уникальные имена тестов
    all_tests = set()
    for data in datasets.values():
        if 'fio' in data:
            all_tests.update(data['fio'].keys())
    all_tests = sorted(all_tests)
    
    # Создаем цветовую схему для каждого типа хранилища
    storage_types = {}
    for label in datasets.keys():
        storage_type = get_storage_type(label)
        if storage_type not in storage_types:
            storage_types[storage_type] = []
        storage_types[storage_type].append((label, datasets[label]))
    
    # График IOPS
    fig, ax = plt.subplots(figsize=(14, 8))
    x = np.arange(len(all_tests))
    width = 0.8 / len(storage_types)
    
    for idx, (storage_type, data_list) in enumerate(storage_types.items()):
        iops_values = []
        iops_errors = []
        for test in all_tests:
            avg_iops = []
            for _, data in data_list:
                if test in data.get('fio', {}):
                    avg_iops.append(data['fio'][test]['IOPS_mean'])
            iops_values.append(np.mean(avg_iops) if avg_iops else 0)
            iops_errors.append(np.std(avg_iops) if len(avg_iops) > 1 else 0)
        
        offset = width * idx - width * (len(storage_types) - 1) / 2
        color = get_color_for_storage(storage_type)
        bars = ax.bar(x + offset, iops_values, width, 
                      label=storage_type.upper(), 
                      yerr=iops_errors, 
                      capsize=5, 
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                     f'{height:.1f}',
                     ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('IOPS (тысячи)', fontsize=12)
    ax.set_title('Сравнение IOPS между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in all_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_iops_comparison.png'), dpi=300)
    plt.close()
    
    # График Bandwidth
    fig, ax = plt.subplots(figsize=(14, 8))
    for idx, (storage_type, data_list) in enumerate(storage_types.items()):
        bw_values = []
        bw_errors = []
        for test in all_tests:
            avg_bw = []
            for _, data in data_list:
                if test in data.get('fio', {}):
                    avg_bw.append(data['fio'][test]['Bandwidth_mean'])
            bw_values.append(np.mean(avg_bw) if avg_bw else 0)
            bw_errors.append(np.std(avg_bw) if len(avg_bw) > 1 else 0)
        
        offset = width * idx - width * (len(storage_types) - 1) / 2
        color = get_color_for_storage(storage_type)
        bars = ax.bar(x + offset, bw_values, width,
                      label=storage_type.upper(),
                      yerr=bw_errors,
                      capsize=5,
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                     f'{height:.1f}',
                     ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('Bandwidth (MiB/s)', fontsize=12)
    ax.set_title('Сравнение Bandwidth между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in all_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_bandwidth_comparison.png'), dpi=300)
    plt.close()
    
    # График Latency
    fig, ax = plt.subplots(figsize=(14, 8))
    for idx, (storage_type, data_list) in enumerate(storage_types.items()):
        lat_values = []
        lat_errors = []
        for test in all_tests:
            avg_lat = []
            for _, data in data_list:
                if test in data.get('fio', {}):
                    avg_lat.append(data['fio'][test]['Latency_mean'])
            lat_values.append(np.mean(avg_lat) if avg_lat else 0)
            lat_errors.append(np.std(avg_lat) if len(avg_lat) > 1 else 0)
        
        offset = width * idx - width * (len(storage_types) - 1) / 2
        color = get_color_for_storage(storage_type)
        bars = ax.bar(x + offset, lat_values, width,
                      label=storage_type.upper(),
                      yerr=lat_errors,
                      capsize=5,
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                     f'{height:.1f}',
                     ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Сравнение задержки между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in all_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_latency_comparison.png'), dpi=300)
    plt.close()
    
    print("✅ Улучшенные графики FIO созданы")

def plot_pgbench_comparison(datasets, output_dir):
    """Создает графики сравнения pgbench тестов с цветовой схемой"""
    # Фильтруем датасеты с данными pgbench
    pgbench_data = {label: data for label, data in datasets.items() 
                    if 'pgbench' in data and data['pgbench']}
    if not pgbench_data:
        print("⚠️  Нет данных pgbench для визуализации")
        return
    
    # Группируем данные по типу хранилища
    storage_types = {}
    for label, data in pgbench_data.items():
        storage_type = get_storage_type(label)
        if storage_type not in storage_types:
            storage_types[storage_type] = []
        storage_types[storage_type].append((label, data))
    
    if not storage_types:
        print("⚠️  Нет данных pgbench для визуализации")
        return
    
    # Создаем два графика в одной фигуре
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График TPS
    x = np.arange(len(storage_types))
    width = 0.35
    storage_names = list(storage_types.keys())
    
    # Собираем данные для TPS
    tps_values = []
    tps_errors = []
    for storage_type in storage_names:
        values = [d['pgbench']['TPS_mean'] for _, d in storage_types[storage_type]]
        tps_values.append(np.mean(values))
        tps_errors.append(np.std(values) if len(values) > 1 else 0)
    
    # Рисуем столбцы для TPS
    for i, storage_type in enumerate(storage_names):
        color = get_color_for_storage(storage_type)
        ax1.bar(x[i], tps_values[i], width, 
                yerr=tps_errors[i], 
                capsize=10, 
                color=color,
                alpha=0.8)
        
        # Добавляем значения на столбцы
        height = tps_values[i]
        ax1.text(x[i], height + (height * 0.05),
                 f'{height:.0f} ± {tps_errors[i]:.0f}',
                 ha='center', va='bottom', fontsize=9)
    
    ax1.set_xlabel('Тип хранилища', fontsize=12)
    ax1.set_ylabel('TPS (транзакций в секунду)', fontsize=12)
    ax1.set_title('Сравнение TPS (pgbench)', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([s.upper() for s in storage_names])
    ax1.grid(axis='y', alpha=0.3)
    
    # График задержки
    # Собираем данные для задержки
    lat_values = []
    lat_errors = []
    for storage_type in storage_names:
        values = [d['pgbench']['Latency_Avg_mean'] for _, d in storage_types[storage_type]]
        lat_values.append(np.mean(values))
        lat_errors.append(np.std(values) if len(values) > 1 else 0)
    
    # Рисуем столбцы для задержки
    for i, storage_type in enumerate(storage_names):
        color = get_color_for_storage(storage_type)
        ax2.bar(x[i], lat_values[i], width, 
                yerr=lat_errors[i], 
                capsize=10, 
                color=color,
                alpha=0.8)
        
        # Добавляем значения на столбцы
        height = lat_values[i]
        ax2.text(x[i], height + (height * 0.05),
                 f'{height:.2f} ± {lat_errors[i]:.2f}',
                 ha='center', va='bottom', fontsize=9)
    
    ax2.set_xlabel('Тип хранилища', fontsize=12)
    ax2.set_ylabel('Средняя задержка (ms)', fontsize=12)
    ax2.set_title('Сравнение задержки (pgbench)', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([s.upper() for s in storage_names])
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'pgbench_comparison.png'), dpi=300)
    plt.close()
    
    print("✅ Улучшенные графики pgbench созданы")

def plot_scalability(datasets, output_dir):
    """Создает графики масштабируемости (зависимость от количества ВМ)"""
    # Группируем по количеству ВМ
    vm_groups = {}
    for label, data in datasets.items():
        num_vms = data.get('num_vms', 1)
        if num_vms not in vm_groups:
            vm_groups[num_vms] = []
        vm_groups[num_vms].append((label, data))
    
    if len(vm_groups) < 2:
        print("⚠️  Недостаточно данных для анализа масштабируемости")
        return
    
    vm_counts = sorted(vm_groups.keys())
    # Выбираем несколько ключевых тестов для анализа
    key_tests = ['Sequential Read', 'Sequential Write', 'Random Read', 'Random Write']
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, test_name in enumerate(key_tests):
        ax = axes[idx]
        iops_by_vms = []
        for vm_count in vm_counts:
            # Берем среднее по всем датасетам с данным количеством ВМ
            iops_values = []
            for label, data in vm_groups[vm_count]:
                if test_name in data.get('fio', {}):
                    iops_values.append(data['fio'][test_name]['IOPS_mean'])
            if iops_values:
                iops_by_vms.append(sum(iops_values) / len(iops_values))
            else:
                iops_by_vms.append(0)
        
        # Определяем тип хранилища для легенды
        storage_types = set()
        for label in datasets.keys():
            storage_type = get_storage_type(label)
            storage_types.add(storage_type)
        
        storage_type_str = " и ".join([s.upper() for s in storage_types])
        
        ax.plot(vm_counts, iops_by_vms, marker='o', linewidth=2, markersize=10)
        ax.set_xlabel('Количество ВМ', fontsize=11)
        ax.set_ylabel('IOPS (тысячи)', fontsize=11)
        ax.set_title(f'Масштабируемость: {test_name}\n({storage_type_str})', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Добавляем значения на точки
        for x, y in zip(vm_counts, iops_by_vms):
            ax.annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                       xytext=(0,10), ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'scalability_analysis.png'), dpi=300)
    plt.close()
    print("✅ График масштабируемости создан")

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 visualize_results.py <папка1> [папка2] ...")
        print("\nПример:")
        print("  python3 visualize_results.py results/*/")
        print("  python3 visualize_results.py results/20251203_1121_iscsi_1vms_2iter results/20251203_1230_local_1vms_2iter")
        sys.exit(1)
    
    # Ищем файлы агрегированных данных в указанных директориях
    datasets = {}
    for dir_path in sys.argv[1:]:
        # Ищем файл агрегированных данных
        agg_file = os.path.join(dir_path, "aggregated_report.json")
        if os.path.exists(agg_file):
            data = load_aggregated_data(agg_file)
            if data:
                # Используем имя директории как метку
                label = os.path.basename(os.path.normpath(dir_path))
                datasets[label] = data
                print(f"✅ Загружен: {agg_file} -> {label}")
        else:
            print(f"⚠️  Файл агрегированных данных не найден: {agg_file}")
            print("   Нужно сначала выполнить агрегацию результатов:")
            print(f"   python3 aggregate_results.py {dir_path}")
    
    if not datasets:
        print("❌ Не удалось найти агрегированные данные")
        print("   Проверьте, что вы указали правильные директории")
        print("   и выполнили агрегацию результатов с помощью aggregate_results.py")
        sys.exit(1)
    
    # Создаем директорию для графиков
    output_dir = "visualization_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n📊 Создание графиков в: {output_dir}/")
    
    # Создаем графики
    plot_fio_comparison(datasets, output_dir)
    plot_pgbench_comparison(datasets, output_dir)
    plot_scalability(datasets, output_dir)
    
    print(f"\n✅ Визуализация завершена!")
    print(f"📁 Графики сохранены в: {output_dir}/")
    print("\nСозданные файлы:")
    for file in sorted(os.listdir(output_dir)):
        if file.endswith('.png'):
            print(f"  • {file}")

if __name__ == "__main__":
    main()