"""Compare two XML dive files to verify they contain the same dive data."""
import xml.etree.ElementTree as ET
import sys

def parse_reference(path):
    """Parse the Mares exportTrak XML format (inmersiones.xml)."""
    tree = ET.parse(path)
    root = tree.getroot()
    dives = []

    for dive_el in root.findall('.//dive'):
        d = {}
        d['number'] = int(dive_el.findtext('number', '0'))
        d['maxdepth'] = float(dive_el.findtext('maxDepth', '0'))
        d['avgdepth'] = float(dive_el.findtext('avgDepth', '0'))
        d['mintemp'] = float(dive_el.findtext('minTemp', '0'))
        d['maxtemp'] = float(dive_el.findtext('maxTemp', '0'))

        # immersion has start/duration
        imm = dive_el.find('immersion')
        if imm is not None:
            d['start'] = imm.findtext('start', '')
            d['duration'] = imm.findtext('duration', '')
        else:
            d['start'] = ''
            d['duration'] = ''

        # Parse dive profiles (samples)
        samples = []
        profiles = dive_el.find('diveProfiles')
        if profiles is not None:
            for dp in profiles.findall('diveProfile'):
                depth = float(dp.findtext('diveProfileDepth', '0'))
                temp = float(dp.findtext('diveProfileTemperature', '0'))
                time_s = float(dp.findtext('diveProfileTime', '0')) / 1000.0
                samples.append({
                    'time': time_s,
                    'depth': depth,
                    'temp': temp,
                })
        d['samples'] = samples
        d['sample_count'] = len(samples)

        # Gas mix
        tanks = dive_el.find('diveTanks')
        if tanks is not None:
            for tank in tanks.findall('diveTank'):
                d['o2'] = float(tank.findtext('o2', '21'))
                d['he'] = float(tank.findtext('he', '0'))
                break

        dives.append(d)

    return dives


def parse_our_export(path):
    """Parse our dc_zip_converter XML format (dives.xml)."""
    tree = ET.parse(path)
    root = tree.getroot()
    dives = []

    for dive_el in root.findall('dive'):
        d = {}
        d['number'] = int(dive_el.findtext('number', '0'))
        d['maxdepth'] = float(dive_el.findtext('maxdepth', '0'))
        d['avgdepth'] = float(dive_el.findtext('avgdepth', '0'))

        # Temperatures
        for temp_el in dive_el.findall('temperature'):
            ttype = temp_el.get('type', '')
            val = float(temp_el.text or '0')
            if ttype == 'minimum':
                d['mintemp'] = val
            elif ttype == 'maximum':
                d['maxtemp'] = val

        d['datetime'] = dive_el.findtext('datetime', '')
        d['divetime_seconds'] = int(dive_el.findtext('divetime_seconds', '0'))

        # Samples
        samples = []
        for s in dive_el.findall('sample'):
            time_str = s.findtext('time', '0:00')
            depth = float(s.findtext('depth', '0'))
            temp = float(s.findtext('temperature', '0'))
            # Parse mm:ss time
            parts = time_str.split(':')
            time_s = int(parts[0]) * 60 + int(parts[1])
            samples.append({
                'time': time_s,
                'depth': depth,
                'temp': temp,
            })
        d['samples'] = samples
        d['sample_count'] = len(samples)

        # Gas mix
        gm = dive_el.find('gasmix')
        if gm is not None:
            d['o2'] = float(gm.findtext('o2', '21'))
            d['he'] = float(gm.findtext('he', '0'))

        dives.append(d)

    return dives


def compare_dives(ref_dives, our_dives):
    """Compare two lists of dives."""
    print(f"{'='*80}")
    print(f"COMPARACION DE ARCHIVOS XML DE INMERSIONES")
    print(f"{'='*80}")
    print(f"\nReferencia (inmersiones.xml): {len(ref_dives)} buceos")
    print(f"Nuestro export (dives.xml):   {len(our_dives)} buceos")
    print()

    if len(ref_dives) != len(our_dives):
        print("[ERROR] Diferente numero de buceos!")
        return

    print(f"[OK] Ambos archivos contienen {len(ref_dives)} buceos\n")

    # Sort both by dive number
    ref_dives.sort(key=lambda x: x['number'])
    our_dives.sort(key=lambda x: x['number'])

    total_issues = 0
    total_checks = 0

    for i, (ref, ours) in enumerate(zip(ref_dives, our_dives)):
        print(f"{'-'*80}")
        print(f"BUCEO #{ref['number']}")
        print(f"{'-'*80}")

        issues = 0

        # Compare dive number
        total_checks += 1
        if ref['number'] != ours['number']:
            print(f"  [DIFF] Numero: REF={ref['number']} vs OURS={ours['number']}")
            issues += 1
        else:
            print(f"  [OK] Numero de buceo: {ref['number']}")

        # Compare max depth
        total_checks += 1
        diff = abs(ref['maxdepth'] - ours['maxdepth'])
        if diff > 0.2:
            print(f"  [DIFF] Prof. max: REF={ref['maxdepth']:.1f}m vs OURS={ours['maxdepth']:.1f}m (diff={diff:.1f}m)")
            issues += 1
        else:
            print(f"  [OK] Prof. max: REF={ref['maxdepth']:.1f}m vs OURS={ours['maxdepth']:.1f}m")

        # Compare avg depth
        total_checks += 1
        diff = abs(ref['avgdepth'] - ours['avgdepth'])
        if diff > 0.5:
            print(f"  [DIFF] Prof. avg: REF={ref['avgdepth']:.1f}m vs OURS={ours['avgdepth']:.1f}m (diff={diff:.1f}m)")
            issues += 1
        else:
            print(f"  [OK] Prof. avg: REF={ref['avgdepth']:.1f}m vs OURS={ours['avgdepth']:.1f}m")

        # Compare temperatures
        total_checks += 1
        ref_mint = ref.get('mintemp', 0)
        our_mint = ours.get('mintemp', 0)
        diff = abs(ref_mint - our_mint)
        if diff > 0.5:
            print(f"  [DIFF] Temp min: REF={ref_mint:.1f}C vs OURS={our_mint:.1f}C (diff={diff:.1f})")
            issues += 1
        else:
            print(f"  [OK] Temp min: REF={ref_mint:.1f}C vs OURS={our_mint:.1f}C")

        total_checks += 1
        ref_maxt = ref.get('maxtemp', 0)
        our_maxt = ours.get('maxtemp', 0)
        diff = abs(ref_maxt - our_maxt)
        if diff > 0.5:
            print(f"  [DIFF] Temp max: REF={ref_maxt:.1f}C vs OURS={our_maxt:.1f}C (diff={diff:.1f})")
            issues += 1
        else:
            print(f"  [OK] Temp max: REF={ref_maxt:.1f}C vs OURS={our_maxt:.1f}C")

        # Compare sample count
        total_checks += 1
        ref_sc = ref['sample_count']
        our_sc = ours['sample_count']
        if ref_sc != our_sc:
            print(f"  [DIFF] Muestras: REF={ref_sc} vs OURS={our_sc}")
            issues += 1
        else:
            print(f"  [OK] Muestras: {ref_sc}")

        # Compare sample data (depth profiles)
        if ref_sc > 0 and our_sc > 0:
            # Compare depth at each matching time
            ref_by_time = {int(s['time']): s for s in ref['samples']}
            our_by_time = {int(s['time']): s for s in ours['samples']}
            
            common_times = sorted(set(ref_by_time.keys()) & set(our_by_time.keys()))
            
            depth_diffs = []
            temp_diffs = []
            for t in common_times:
                dd = abs(ref_by_time[t]['depth'] - our_by_time[t]['depth'])
                td = abs(ref_by_time[t]['temp'] - our_by_time[t]['temp'])
                depth_diffs.append(dd)
                temp_diffs.append(td)

            total_checks += 1
            if common_times:
                max_dd = max(depth_diffs)
                avg_dd = sum(depth_diffs)/len(depth_diffs)
                max_td = max(temp_diffs)
                avg_td = sum(temp_diffs)/len(temp_diffs)

                if max_dd > 0.5:
                    print(f"  [DIFF] Perfil profundidad: max_diff={max_dd:.1f}m avg_diff={avg_dd:.2f}m")
                    # Show worst mismatches
                    worst = sorted(zip(common_times, depth_diffs), key=lambda x: -x[1])[:3]
                    for t, dd in worst:
                        print(f"         t={t}s: REF={ref_by_time[t]['depth']:.1f}m vs OURS={our_by_time[t]['depth']:.1f}m")
                    issues += 1
                else:
                    print(f"  [OK] Perfil profundidad: max_diff={max_dd:.2f}m avg_diff={avg_dd:.3f}m ({len(common_times)} pts comparados)")

                total_checks += 1
                if max_td > 1.0:
                    print(f"  [DIFF] Perfil temperatura: max_diff={max_td:.1f}C avg_diff={avg_td:.2f}C")
                    issues += 1
                else:
                    print(f"  [OK] Perfil temperatura: max_diff={max_td:.2f}C avg_diff={avg_td:.3f}C ({len(common_times)} pts comparados)")
            else:
                print(f"  [WARN] No hay tiempos comunes para comparar perfiles")

        # Gas mix
        if 'o2' in ref and 'o2' in ours:
            total_checks += 1
            if abs(ref['o2'] - ours['o2']) > 0.5:
                print(f"  [DIFF] O2: REF={ref['o2']:.0f}% vs OURS={ours['o2']:.0f}%")
                issues += 1
            else:
                print(f"  [OK] O2: {ref['o2']:.0f}%")

        if issues == 0:
            print(f"  >>> BUCEO #{ref['number']}: TODOS LOS DATOS COINCIDEN <<<")
        else:
            print(f"  >>> BUCEO #{ref['number']}: {issues} DIFERENCIA(S) ENCONTRADA(S) <<<")
        
        total_issues += issues
        print()

    print(f"{'='*80}")
    print(f"RESUMEN FINAL")
    print(f"{'='*80}")
    print(f"  Buceos comparados: {len(ref_dives)}")
    print(f"  Verificaciones: {total_checks}")
    print(f"  Diferencias: {total_issues}")
    if total_issues == 0:
        print(f"\n  [OK] TODOS LOS DATOS COINCIDEN ENTRE AMBOS ARCHIVOS")
    else:
        print(f"\n  [!!] HAY {total_issues} DIFERENCIA(S) A REVISAR")


if __name__ == '__main__':
    ref_path = r'C:\Users\dante\Downloads\inmersiones.xml'
    our_path = r'C:\Users\dante\Downloads\puck4_export\dives.xml'

    ref_dives = parse_reference(ref_path)
    our_dives = parse_our_export(our_path)
    compare_dives(ref_dives, our_dives)
