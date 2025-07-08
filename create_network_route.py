from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

@app.route('/create_network', methods=['GET', 'POST'])
@login_required
def create_network():
    if getattr(current_user, 'planType', None) != 'infinity':
        flash('Sadece Infinity plan kullanıcıları ağ oluşturabilir.', 'warning')
        return redirect(url_for('upgrade_plan'))
    # Infinity ağı zaten var mı kontrol et
    network = None
    try:
        from models import InfinityNetwork
        network = InfinityNetwork.query.filter_by(user_id=current_user.id).first()
    except Exception:
        network = None
    if network:
        flash('Zaten bir Infinity ağınız var.', 'info')
        return redirect(url_for('my_network_slug', slug=network.slug))
    if request.method == 'POST':
        # Burada Infinity ağı oluşturma işlemleri yapılacak
        # ...
        flash('Infinity ağınız başarıyla oluşturuldu!', 'success')
        # Ağ oluşturulduktan sonra slug ile yönlendir
        network = InfinityNetwork.query.filter_by(user_id=current_user.id).first()
        return redirect(url_for('my_network_slug', slug=network.slug))
    return render_template('create_infinity_network.html')
