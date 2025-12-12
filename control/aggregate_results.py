#!/usr/bin/env python3
"""
Скрипт для агрегации результатов множественных итераций тестирования.
Вычисляет средние значения, стандартные отклонения и создает сводные отчеты.
"""
import os
import re
import json
import sys
from pathlib import Path
from statistics import mean, stdev
from datetime import datetime

ef parse_results_sheet(file_path):
    """Парсит файл results_sheet и извлекает метрики с сохранением форматирования"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        results = {'fio': {}, 'pgbench': {}}
        
        # Ищем раздел с основными результатами
        main_start = content.find("Основные результаты тестов:")
        if main_start == -1:
            print(f"⚠️ Не найден раздел 'Основные результаты тестов' в файле {file_path}")
            return None
            
        # Ищем конец раздела основных результатов
        latency_start = content.find("Детализированная информация о задержках:")
        if latency_start == -1:
            end_pos = len(content)
        else:
            end_pos = latency_start
        
        main_content = content[main_start:end_pos]
        
        # Разбиваем на строки и обрабатываем каждую
        lines = main_content.split('\n')
        current_test_number = 0
        current_test_name = ""
        
        for line in lines:
            # Пропускаем заголовки, разделители и пустые строки
            if not line.strip() or "Test No." in line or "=" in line or "_" in line:
                continue
            
            # Обрабатываем строку с данными
            parts = [p.strip() for p in line.split() if p.strip()]
            
            # Пропускаем строки, которые не содержат достаточно данных
            if len(parts) < 5:
                continue
            
            # Проверяем, начинается ли строка с цифры (номер теста)
            if parts[0].isdigit():
                current_test_number = int(parts[0])
                current_test_name = " ".join(parts[1:-3])
                iops = parts[-3]
                bandwidth = parts[-2]
                latency = parts[-1]
                
                # Добавляем тест в результаты
                results['fio'][current_test_name] = {
                    'IOPS': float(iops),
                    'Bandwidth': float(bandwidth),
                    'Latency': float(latency)
                }
            else:
                # Если строка не начинается с цифры, это продолжение предыдущего теста
                # (например, Mixed RW имеет две строки с номером 5)
                current_test_name = " ".join(parts[:-3])
                iops = parts[-3]
                bandwidth = parts[-2]
                latency = parts[-1]
                
                # Формируем уникальное имя для дублирующихся номеров тестов
                unique_name = f"{current_test_name} ({parts[0]})"
                results['fio'][unique_name] = {
                    'IOPS': float(iops),
                    'Bandwidth': float(bandwidth),
                    'Latency': float(latency)
                }
        
        # Парсинг pgbench остается без изменений
        pgbench_pattern = r'TPS.*?:\s*([\d.]+).*?Средняя задержка:\s*([\d.]+).*?Обработано транзакций:\s*(\d+)'
        pg_match = re.search(pgbench_pattern, content, re.DOTALL)
        if pg_match:
            results['pgbench'] = {
                'TPS': float(pg_match.group(1)),
                'Latency_Avg': float(pg_match.group(2)),
                'Transactions': int(pg_match.group(3))
            }
        
        return results
    except Exception as e:
        print(f"⚠️ Ошибка парсинга {file_path}: {e}")
        return None

def aggregate_results(results_dir):
    """Агрегирует результаты всех итераций с сохранением оригинальных названий тестов"""
    results_dir = Path(results_dir)
    iterations_data = {}
    
    # Собираем все файлы результатов
    for subdir in results_dir.iterdir():
        if not subdir.is_dir():
            continue
        for file in subdir.glob('results_sheet_*.txt'):
            iter_match = re.search(r'iter(\d+)', str(subdir))
            if iter_match:
                iter_num = int(iter_match.group(1))
                parsed = parse_results_sheet(file)
                if parsed:
                    if iter_num not in iterations_data:
                        iterations_data[iter_num] = []
                    iterations_data[iter_num].append(parsed)
    
    if not iterations_data:
        print("❌ Не найдено результатов для агрегации")
        return None
    
    aggregated = {
        'fio': {},
        'pgbench': {},
        'iterations': sorted(iterations_data.keys()),
        'num_vms': len(iterations_data[list(iterations_data.keys())[0]])
    }
    
    # Собираем все уникальные названия тестов
    all_test_names = set()
    for iter_results in iterations_data.values():
        for vm_result in iter_results:
            all_test_names.update(vm_result['fio'].keys())
    
    # Агрегируем данные для каждого теста с сохранением оригинальных названий
    for test_name in sorted(all_test_names):
        metrics = {'IOPS': [], 'Bandwidth': [], 'Latency': []}
        for iter_results in iterations_data.values():
            for vm_result in iter_results:
                if test_name in vm_result['fio']:
                    metrics['IOPS'].append(vm_result['fio'][test_name]['IOPS'])
                    metrics['Bandwidth'].append(vm_result['fio'][test_name]['Bandwidth'])
                    metrics['Latency'].append(vm_result['fio'][test_name]['Latency'])
        
        if metrics['IOPS']:  # если есть данные для этого теста
            aggregated['fio'][test_name] = {
                'IOPS_mean': mean(metrics['IOPS']),
                'IOPS_stdev': stdev(metrics['IOPS']) if len(metrics['IOPS']) > 1 else 0,
                'Bandwidth_mean': mean(metrics['Bandwidth']),
                'Bandwidth_stdev': stdev(metrics['Bandwidth']) if len(metrics['Bandwidth']) > 1 else 0,
                'Latency_mean': mean(metrics['Latency']),
                'Latency_stdev': stdev(metrics['Latency']) if len(metrics['Latency']) > 1 else 0,
                'samples': len(metrics['IOPS'])
            }
        else:
            print(f"⚠️ Не удалось собрать данные для теста {test_name}")
    
    # Агрегация pgbench остается без изменений
    pgbench_metrics = {'TPS': [], 'Latency_Avg': [], 'Latency_Stddev': [], 'Transactions': []}
    pgbench_found = False
    
    for iter_results in iterations_data.values():
        for vm_result in iter_results:
            if 'pgbench' in vm_result and vm_result['pgbench']:
                pgbench_found = True
                for metric, values in pgbench_metrics.items():
                    if vm_result['pgbench'].get(metric) is not None:
                        values.append(vm_result['pgbench'][metric])
    
    if pgbench_found and pgbench_metrics['TPS']:
        aggregated['pgbench'] = {
            'TPS_mean': mean(pgbench_metrics['TPS']),
            'TPS_stdev': stdev(pgbench_metrics['TPS']) if len(pgbench_metrics['TPS']) > 1 else 0,
            'Latency_Avg_mean': mean(pgbench_metrics['Latency_Avg']),
            'Latency_Avg_stdev': stdev(pgbench_metrics['Latency_Avg']) if len(pgbench_metrics['Latency_Avg']) > 1 else 0,
            'samples': len(pgbench_metrics['TPS'])
        }
    
    return aggregated

def generate_report(aggregated, output_file):
    """Генерирует текстовый отчет"""
    report = []
    report.append("="*80)
    report.append("АГРЕГИРОВАННЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    report.append("="*80)
    report.append(f"Дата создания отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Количество итераций: {len(aggregated['iterations'])}")
    report.append(f"Количество ВМ: {aggregated['num_vms']}")
    report.append("")
    
    # FIO результаты
    if aggregated['fio']:
        report.append("="*80)
        report.append("FIO - Тестирование дисковой подсистемы (средние значения)")
        report.append("="*80)
        report.append("")
        report.append(f"{'Test Name':<35} {'IOPS':<20} {'Bandwidth (MiB/s)':<20} {'Latency (ms)':<20}")
        report.append("-"*80)
        for test_name, metrics in sorted(aggregated['fio'].items()):
            report.append(
                f"{test_name:<35} "
                f"{metrics['IOPS_mean']:>8.1f} ±{metrics['IOPS_stdev']:>6.1f}  "
                f"{metrics['Bandwidth_mean']:>8.1f} ±{metrics['Bandwidth_stdev']:>6.1f}  "
                f"{metrics['Latency_mean']:>8.2f} ±{metrics['Latency_stdev']:>6.2f}"
            )
        report.append("")
    
    # pgbench результаты
    if 'pgbench' in aggregated and aggregated['pgbench']:
        report.append("="*80)
        report.append("pgbench - Тестирование PostgreSQL OLTP (средние значения)")
        report.append("="*80)
        report.append("")
        pg = aggregated['pgbench']
        report.append(f"TPS (Transactions Per Second): {pg['TPS_mean']:.2f} ± {pg['TPS_stdev']:.2f}")
        report.append(f"Средняя задержка: {pg['Latency_Avg_mean']:.3f} ± {pg['Latency_Avg_stdev']:.3f} ms")
        report.append(f"Количество измерений: {pg['samples']}")
        report.append("")
    else:
        report.append("="*80)
        report.append("pgbench - Тестирование PostgreSQL OLTP")
        report.append("="*80)
        report.append("")
        report.append("ℹ️  Результаты pgbench отсутствуют (тест не запускался или не был включен)")
        report.append("")
    
    report.append("="*80)
    report.append("Примечание: Значения указаны в формате 'среднее ± стандартное отклонение'")
    report.append("="*80)
    
    report_text = "\n".join(report)
    
    # Вывод в консоль
    print(report_text)
    
    # Сохранение в файл
    with open(output_file, 'w') as f:
        f.write(report_text)
    print(f"\n📄 Отчет сохранен: {output_file}")
    return report_text

def save_json(aggregated, output_file):
    """Сохраняет агрегированные данные в JSON"""
    with open(output_file, 'w') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)
    print(f"📊 JSON данные сохранены: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 aggregate_results.py <путь_к_директории_с_результатами> [путь_2] ...")
        print("\nПримеры:")
        print("  python3 aggregate_results.py results/20251203_1121_iscsi_1vms_2iter/")
        print("  python3 aggregate_results.py results/*/")
        sys.exit(1)
    
    # Обработка нескольких директорий
    for results_dir in sys.argv[1:]:
        if not os.path.exists(results_dir):
            print(f"❌ Директория не найдена: {results_dir}")
            continue
        
        print(f"\n{'='*60}")
        print(f"📁 Анализ результатов в: {results_dir}")
        print("⏳ Обработка данных...")
        
        aggregated = aggregate_results(results_dir)
        if not aggregated:
            print("❌ Не удалось агрегировать результаты")
            continue
        
        # Генерация отчетов
        output_base = os.path.join(results_dir, "aggregated_report")
        generate_report(aggregated, f"{output_base}.txt")
        save_json(aggregated, f"{output_base}.json")
    
    print(f"\n{'='*60}")
    print("✅ Агрегация завершена для всех директорий!")

if __name__ == "__main__":
    main()