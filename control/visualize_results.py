#!/usr/bin/env python3
"""
Скрипт для визуализации результатов тестирования.
Создает графики для сравнения результатов между разными конфигурациями.
"""
import json
import sys
import os
import glob
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

def load_aggregated_data(json_file):
    """Загружает агрегированные данные из JSON"""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки {json_file}: {str(e)}")
        return None

def plot_fio_comparison(datasets, output_dir):
    """Создает графики сравнения FIO тестов с фильтрацией ненужных данных"""
    # Определяем список допустимых тестов
    valid_tests = [
        "Sequential Write",
        "Sequential Read", 
        "Random Write",
        "Random Read",
        "Mixed RW (Read)",
        "Mixed RW (Write)",
        "Sequential Read"
    ]
    
    # Собираем данные по всем тестам
    all_tests = set()
    for data in datasets.values():
        if 'fio' in data:
            all_tests.update(data['fio'].keys())
    
    # Фильтруем только допустимые тесты
    filtered_tests = [test for test in all_tests if test in valid_tests]
    
    # Сортируем тесты в нужном порядке
    test_order = {test: idx for idx, test in enumerate(valid_tests)}
    filtered_tests = sorted(filtered_tests, key=lambda x: test_order.get(x, 999))
    
    if not filtered_tests:
        print("⚠️  Нет данных для отображения. Проверьте, что в данных есть тесты из списка допустимых.")
        return
    
    # График IOPS
    fig, ax = plt.subplots(figsize=(14, 8))
    x = range(len(filtered_tests))
    width = 0.8 / len(datasets)
    
    # Для каждого типа хранилища
    for idx, (label, data) in enumerate(datasets.items()):
        storage_type = get_storage_type(label)
        color = get_color_for_storage(storage_type)
        
        iops_values = []
        iops_errors = []
        for test in filtered_tests:
            if test in data.get('fio', {}):
                iops_values.append(data['fio'][test]['IOPS_mean'])
                iops_errors.append(data['fio'][test]['IOPS_stdev'])
            else:
                iops_values.append(0)
                iops_errors.append(0)
        
        offset = width * idx - width * (len(datasets) - 1) / 2
        bars = ax.bar([i + offset for i in x], iops_values, width,
                      label=storage_type.upper(),
                      yerr=iops_errors,
                      capsize=5,
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы с проверкой высоты
        for i, bar in enumerate(bars):
            height = bar.get_height()
            # Если высота превышает 80% от верхней границы, уменьшаем размер шрифта
            if height > 0.8 * ax.get_ylim()[1]:
                fontsize = 7
            else:
                fontsize = 9
            # Добавляем значение над столбцом
            ax.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=fontsize)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('IOPS (тысячи)', fontsize=12)
    ax.set_title('Сравнение IOPS между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in filtered_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_iops_comparison.png'), dpi=300)
    plt.close()
    
    # График Bandwidth
    fig, ax = plt.subplots(figsize=(14, 8))
    for idx, (label, data) in enumerate(datasets.items()):
        storage_type = get_storage_type(label)
        color = get_color_for_storage(storage_type)
        
        bw_values = []
        bw_errors = []
        for test in filtered_tests:
            if test in data.get('fio', {}):
                bw_values.append(data['fio'][test]['Bandwidth_mean'])
                bw_errors.append(data['fio'][test]['Bandwidth_stdev'])
            else:
                bw_values.append(0)
                bw_errors.append(0)
        
        offset = width * idx - width * (len(datasets) - 1) / 2
        bars = ax.bar([i + offset for i in x], bw_values, width,
                      label=storage_type.upper(),
                      yerr=bw_errors,
                      capsize=5,
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы с проверкой высоты
        for i, bar in enumerate(bars):
            height = bar.get_height()
            # Если высота превышает 80% от верхней границы, уменьшаем размер шрифта
            if height > 0.8 * ax.get_ylim()[1]:
                fontsize = 7
            else:
                fontsize = 9
            # Добавляем значение над столбцом
            ax.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=fontsize)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('Bandwidth (MiB/s)', fontsize=12)
    ax.set_title('Сравнение Bandwidth между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in filtered_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_bandwidth_comparison.png'), dpi=300)
    plt.close()
    
    # График Latency
    fig, ax = plt.subplots(figsize=(14, 8))
    for idx, (label, data) in enumerate(datasets.items()):
        storage_type = get_storage_type(label)
        color = get_color_for_storage(storage_type)
        
        lat_values = []
        lat_errors = []
        for test in filtered_tests:
            if test in data.get('fio', {}):
                lat_values.append(data['fio'][test]['Latency_mean'])
                lat_errors.append(data['fio'][test]['Latency_stdev'])
            else:
                lat_values.append(0)
                lat_errors.append(0)
        
        offset = width * idx - width * (len(datasets) - 1) / 2
        bars = ax.bar([i + offset for i in x], lat_values, width,
                      label=storage_type.upper(),
                      yerr=lat_errors,
                      capsize=5,
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы с проверкой высоты
        for i, bar in enumerate(bars):
            height = bar.get_height()
            # Если высота превышает 80% от верхней границы, уменьшаем размер шрифта
            if height > 0.8 * ax.get_ylim()[1]:
                fontsize = 7
            else:
                fontsize = 9
            # Добавляем значение над столбцом
            ax.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=fontsize)
    
    ax.set_xlabel('Тип теста', fontsize=12)
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Сравнение задержки между типами хранилищ', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(' ', '\n') for t in filtered_tests], rotation=0, ha='center')
    ax.legend(title='Тип хранилища')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fio_latency_comparison.png'), dpi=300)
    plt.close()
    
    print("✅ Улучшенные графики FIO созданы")

def plot_pgbench_comparison(datasets, output_dir):
    """Создает графики сравнения pgbench тестов с разными цветами для типов хранилищ"""
    # Фильтруем датасеты с данными pgbench
    pgbench_data = {label: data for label, data in datasets.items() 
                    if 'pgbench' in data and data['pgbench']}
    if not pgbench_data:
        print("⚠️  Нет данных pgbench для визуализации")
        return
    
    # Группируем данные по типам хранилищ
    storage_types = {}
    for label, data in pgbench_data.items():
        storage_type = get_storage_type(label)
        if storage_type not in storage_types:
            storage_types[storage_type] = []
        storage_types[storage_type].append((label, data))
    
    # Настраиваем график
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График TPS
    x = range(len(storage_types))
    width = 0.8 / len(storage_types)
    storage_names = list(storage_types.keys())
    
    tps_values = []
    tps_errors = []
    for storage_type in storage_names:
        values = [d['pgbench']['TPS_mean'] for _, d in storage_types[storage_type]]
        tps_values.append(np.mean(values))
        tps_errors.append(np.std(values) if len(values) > 1 else 0)
    
    for idx, storage_type in enumerate(storage_names):
        color = get_color_for_storage(storage_type)
        bar = ax1.bar(idx, tps_values[idx], width, 
                      yerr=tps_errors[idx], 
                      capsize=10, 
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы
        height = tps_values[idx]
        ax1.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.0f}\n±{tps_errors[idx]:.0f}',
                ha='center', va='bottom', fontsize=9)
    
    ax1.set_xlabel('Тип хранилища', fontsize=12)
    ax1.set_ylabel('TPS (транзакций в секунду)', fontsize=12)
    ax1.set_title('Сравнение TPS (pgbench)', fontsize=14, fontweight='bold')
    ax1.set_xticks(range(len(storage_names)))
    ax1.set_xticklabels([s.upper() for s in storage_names])
    ax1.grid(axis='y', alpha=0.3)
    
    # График задержки
    lat_values = []
    lat_errors = []
    for storage_type in storage_names:
        values = [d['pgbench']['Latency_Avg_mean'] for _, d in storage_types[storage_type]]
        lat_values.append(np.mean(values))
        lat_errors.append(np.std(values) if len(values) > 1 else 0)
    
    for idx, storage_type in enumerate(storage_names):
        color = get_color_for_storage(storage_type)
        bar = ax2.bar(idx, lat_values[idx], width, 
                      yerr=lat_errors[idx], 
                      capsize=10, 
                      color=color,
                      alpha=0.8)
        
        # Добавляем значения на столбцы
        height = lat_values[idx]
        ax2.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.2f}\n±{lat_errors[idx]:.2f}',
                ha='center', va='bottom', fontsize=9)
    
    ax2.set_xlabel('Тип хранилища', fontsize=12)
    ax2.set_ylabel('Средняя задержка (ms)', fontsize=12)
    ax2.set_title('Сравнение задержки (pgbench)', fontsize=14, fontweight='bold')
    ax2.set_xticks(range(len(storage_names)))
    ax2.set_xticklabels([s.upper() for s in storage_names])
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'pgbench_comparison.png'), dpi=300)
    plt.close()
    
    print("✅ Улучшенные графики pgbench созданы")

def find_aggregated_reports(paths):
    """Находит файлы aggregated_report.json в указанных путях"""
    reports = []
    
    for path in paths:
        path = Path(path)
        
        # Если это файл, проверяем, не является ли он JSON-отчетом
        if path.is_file() and path.name == 'aggregated_report.json':
            reports.append(str(path))
            continue
            
        # Если это директория, ищем в ней файл aggregated_report.json
        if path.is_dir():
            report_file = path / 'aggregated_report.json'
            if report_file.exists() and report_file.is_file():
                reports.append(str(report_file))
                print(f"✅ Найден файл агрегированных данных: {report_file}")
                continue
                
            # Если в директории нет файла, ищем в поддиректориях
            for subdir in path.iterdir():
                if subdir.is_dir():
                    report_file = subdir / 'aggregated_report.json'
                    if report_file.exists() and report_file.is_file():
                        reports.append(str(report_file))
                        print(f"✅ Найден файл агрегированных данных: {report_file}")
                        continue
            continue
            
        print(f"⚠️  Не удалось найти файл агрегированных данных в: {path}")
    
    return reports

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 visualize_results.py <папка1> [<папка2> ...]")
        print("\nПримеры:")
        print("  python3 visualize_results.py results/*/")
        print("  python3 visualize_results.py results/20251203_1121_iscsi_1vms_2iter results/20251203_1230_local_1vms_2iter")
        sys.exit(1)
    
    # Находим все файлы aggregated_report.json в указанных путях
    report_files = find_aggregated_reports(sys.argv[1:])
    
    if not report_files:
        print("❌ Не удалось найти файлы агрегированных данных")
        print("   Убедитесь, что вы выполнили агрегацию результатов:")
        print("   python3 aggregate_results.py <папка_с_результатами>")
        sys.exit(1)
    
    # Загружаем все JSON файлы
    datasets = {}
    for json_path in report_files:
        data = load_aggregated_data(json_path)
        if data:
            # Извлекаем метку из пути (имя директории)
            parent_dir = Path(json_path).parent
            label = parent_dir.name
            
            # Определяем тип хранилища из имени директории
            storage_type = get_storage_type(label)
            
            # Создаем уникальную метку
            unique_label = f"{storage_type}_{label.split('_')[-3]}vms"
            if unique_label in datasets:
                # Если метка уже существует, добавляем суффикс
                suffix = 1
                while f"{unique_label}_{suffix}" in datasets:
                    suffix += 1
                unique_label = f"{unique_label}_{suffix}"
            
            datasets[unique_label] = data
            print(f"✅ Загружен: {json_path} -> {unique_label}")
    
    if not datasets:
        print("❌ Не удалось загрузить данные")
        sys.exit(1)
    
    # Создаем директорию для графиков
    output_dir = "visualization_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n📊 Создание графиков в: {output_dir}/")
    
    # Создаем графики
    plot_fio_comparison(datasets, output_dir)
    plot_pgbench_comparison(datasets, output_dir)
    
    print(f"\n✅ Визуализация завершена!")
    print(f"📁 Графики сохранены в: {output_dir}/")
    print("\nСозданные файлы:")
    for file in sorted(os.listdir(output_dir)):
        if file.endswith('.png'):
            print(f"  • {file}")

if __name__ == "__main__":
    main()