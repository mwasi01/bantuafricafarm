# CONTINUATION OF app.py - Version 1.1 Corrected
# ============================================================================

    monthly_income = db.session.query(
        func.sum(FarmIncome.total_amount)
    ).filter(
        extract('month', FarmIncome.income_date) == current_month,
        extract('year', FarmIncome.income_date) == current_year
    ).scalar() or 0
    
    monthly_expenses = db.session.query(
        func.sum(FarmExpense.total_amount)
    ).filter(
        extract('month', FarmExpense.expense_date) == current_month,
        extract('year', FarmExpense.expense_date) == current_year
    ).scalar() or 0
    
    # Production stats
    milk_production = db.session.query(
        func.sum(MilkRecord.quantity_litres)
    ).filter(
        extract('month', MilkRecord.milking_date) == current_month,
        extract('year', MilkRecord.milking_date) == current_year
    ).scalar() or 0
    
    # Tasks overview
    task_stats = db.session.query(
        Task.status,
        func.count(Task.id)
    ).group_by(Task.status).all()
    
    # Upcoming tasks
    upcoming_tasks = Task.query.filter(
        Task.due_date >= date.today(),
        Task.status.in_(['Pending', 'In Progress'])
    ).order_by(Task.due_date.asc()).limit(5).all()
    
    # Health alerts
    sick_animals = Livestock.query.filter_by(
        health_status='Sick', 
        is_active=True
    ).count()
    
    return render_template('dashboard.html',
                         total_livestock=total_livestock,
                         total_crops=total_crops,
                         total_employees=total_employees,
                         pending_tasks=pending_tasks,
                         livestock_categories=livestock_categories,
                         recent_activities=recent_activities,
                         monthly_income=monthly_income,
                         monthly_expenses=monthly_expenses,
                         milk_production=milk_production,
                         task_stats=task_stats,
                         upcoming_tasks=upcoming_tasks,
                         sick_animals=sick_animals)

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with advanced analytics"""
    # Comprehensive statistics
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_livestock': Livestock.query.count(),
        'active_crops': CropPlanting.query.filter_by(status='Active').count(),
        'monthly_revenue': db.session.query(func.sum(FarmIncome.total_amount)).filter(
            extract('month', FarmIncome.income_date) == datetime.now().month
        ).scalar() or 0,
        'monthly_expenses': db.session.query(func.sum(FarmExpense.total_amount)).filter(
            extract('month', FarmExpense.expense_date) == datetime.now().month
        ).scalar() or 0,
        'pending_payroll': Payroll.query.filter_by(payment_status='Pending').count(),
        'pending_approvals': Leave.query.filter_by(status='Pending').count()
    }
    
    # Department performance
    dept_performance = db.session.query(
        User.department,
        func.count(Task.id)
    ).join(Task, Task.assigned_to == User.id).filter(
        Task.status == 'Completed'
    ).group_by(User.department).all()
    
    # Monthly trends (last 12 months)
    monthly_trends = []
    for i in range(11, -1, -1):
        month_date = date.today().replace(day=1) - timedelta(days=i*30)
        month_income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
            extract('month', FarmIncome.income_date) == month_date.month,
            extract('year', FarmIncome.income_date) == month_date.year
        ).scalar() or 0
        
        month_expense = db.session.query(func.sum(FarmExpense.total_amount)).filter(
            extract('month', FarmExpense.expense_date) == month_date.month,
            extract('year', FarmExpense.expense_date) == month_date.year
        ).scalar() or 0
        
        monthly_trends.append({
            'month': month_date.strftime('%b %Y'),
            'income': float(month_income),
            'expense': float(month_expense)
        })
    
    return render_template('admin/dashboard.html', 
                         stats=stats,
                         dept_performance=dept_performance,
                         monthly_trends=monthly_trends)

@app.route('/worker/dashboard')
@login_required
def worker_dashboard():
    """Worker-specific dashboard"""
    # Tasks assigned to worker
    my_tasks = Task.query.filter_by(
        assigned_to=current_user.id
    ).order_by(Task.due_date.asc()).limit(10).all()
    
    # Today's attendance
    today_attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        attendance_date=date.today()
    ).first()
    
    # My wages this month
    monthly_wages = db.session.query(
        func.sum(Wage.amount)
    ).filter(
        Wage.user_id == current_user.id,
        extract('month', Wage.wage_date) == datetime.now().month,
        extract('year', Wage.wage_date) == datetime.now().year
    ).scalar() or 0
    
    # My leave balance
    approved_leaves = Leave.query.filter(
        Leave.user_id == current_user.id,
        Leave.status == 'Approved',
        extract('year', Leave.start_date) == datetime.now().year
    ).all()
    
    leave_days_taken = sum(leave.days_requested for leave in approved_leaves)
    leave_balance = 21 - leave_days_taken  # Standard 21 days annual leave
    
    return render_template('worker/dashboard.html',
                         my_tasks=my_tasks,
                         today_attendance=today_attendance,
                         monthly_wages=monthly_wages,
                         leave_balance=leave_balance)

# ============================================================================
# USER MANAGEMENT ROUTES
# ============================================================================

@app.route('/users')
@login_required
@admin_required
def user_list():
    """List all users"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    users = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    departments = db.session.query(User.department).distinct().all()
    roles = db.session.query(User.role).distinct().all()
    
    return render_template('users/list.html', 
                         users=users,
                         departments=[d[0] for d in departments if d[0]],
                         roles=[r[0] for r in roles if r[0]])

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user/employee"""
    if request.method == 'POST':
        # Generate employee ID
        year = datetime.now().year
        count = User.query.count() + 1
        employee_id = f"EMP{year}{count:04d}"
        
        # Handle profile picture
        profile_pic = request.files.get('profile_picture')
        profile_pic_url = None
        if profile_pic and allowed_image(profile_pic.filename):
            profile_pic_url = upload_to_cloudinary(profile_pic, 'employee_photos')
        
        user = User(
            employee_id=employee_id,
            username=request.form.get('username'),
            email=request.form.get('email'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            phone_number=request.form.get('phone_number'),
            national_id=request.form.get('national_id'),
            kra_pin=request.form.get('kra_pin'),
            date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d') if request.form.get('date_of_birth') else None,
            gender=request.form.get('gender'),
            marital_status=request.form.get('marital_status'),
            profile_picture=profile_pic_url,
            role=request.form.get('role', 'worker'),
            department=request.form.get('department'),
            employment_type=request.form.get('employment_type'),
            employment_date=datetime.strptime(request.form.get('employment_date'), '%Y-%m-%d') if request.form.get('employment_date') else date.today(),
            salary_grade=request.form.get('salary_grade'),
            basic_salary=request.form.get('basic_salary'),
            hourly_rate=request.form.get('hourly_rate'),
            nssf_number=request.form.get('nssf_number'),
            nhif_number=request.form.get('nhif_number'),
            bank_name=request.form.get('bank_name'),
            bank_account=request.form.get('bank_account'),
            bank_branch=request.form.get('bank_branch'),
            emergency_contact_name=request.form.get('emergency_contact_name'),
            emergency_contact_phone=request.form.get('emergency_contact_phone'),
            emergency_contact_relation=request.form.get('emergency_contact_relation'),
            home_county=request.form.get('home_county'),
            home_address=request.form.get('home_address'),
            education_level=request.form.get('education_level'),
            certifications=request.form.get('certifications')
        )
        
        user.set_password(request.form.get('password'))
        
        db.session.add(user)
        db.session.commit()
        
        log_activity(current_user.id, 'CREATE_USER', 
                    f'Created user {user.full_name} ({employee_id})', 'HR')
        
        flash(f'Employee {user.full_name} added successfully!', 'success')
        return redirect(url_for('user_list'))
    
    return render_template('users/add.html')

@app.route('/users/<int:user_id>')
@login_required
def user_profile(user_id):
    """View user profile"""
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    tasks_completed = Task.query.filter_by(
        assigned_to=user.id, 
        status='Completed'
    ).count()
    
    attendance_rate = calculate_attendance_rate(user.id)
    
    total_wages = db.session.query(func.sum(Wage.amount)).filter(
        Wage.user_id == user.id
    ).scalar() or 0
    
    return render_template('users/profile.html',
                         user=user,
                         tasks_completed=tasks_completed,
                         attendance_rate=attendance_rate,
                         total_wages=total_wages)

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form.get('username', user.username)
        user.email = request.form.get('email', user.email)
        user.first_name = request.form.get('first_name', user.first_name)
        user.last_name = request.form.get('last_name', user.last_name)
        user.phone_number = request.form.get('phone_number', user.phone_number)
        user.role = request.form.get('role', user.role)
        user.department = request.form.get('department', user.department)
        user.employment_type = request.form.get('employment_type', user.employment_type)
        user.salary_grade = request.form.get('salary_grade', user.salary_grade)
        user.basic_salary = request.form.get('basic_salary', user.basic_salary)
        user.hourly_rate = request.form.get('hourly_rate', user.hourly_rate)
        user.is_active = request.form.get('is_active') == 'on'
        
        # Handle profile picture update
        profile_pic = request.files.get('profile_picture')
        if profile_pic and allowed_image(profile_pic.filename):
            user.profile_picture = upload_to_cloudinary(profile_pic, 'employee_photos')
        
        # Handle password change
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        
        log_activity(current_user.id, 'UPDATE_USER', 
                    f'Updated user {user.full_name}', 'HR')
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('user_profile', user_id=user.id))
    
    return render_template('users/edit.html', user=user)

@app.route('/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_user(user_id):
    """Deactivate user account"""
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    
    log_activity(current_user.id, 'DEACTIVATE_USER', 
                f'Deactivated user {user.full_name}', 'HR')
    
    flash(f'User {user.full_name} has been deactivated.', 'warning')
    return redirect(url_for('user_list'))

# ============================================================================
# LIVESTOCK MANAGEMENT ROUTES
# ============================================================================

@app.route('/livestock')
@login_required
def livestock_list():
    """List all livestock"""
    category_filter = request.args.get('category')
    health_filter = request.args.get('health')
    status_filter = request.args.get('status')
    
    query = Livestock.query.filter_by(is_active=True)
    
    if category_filter:
        query = query.join(LivestockCategory).filter(LivestockCategory.name == category_filter)
    if health_filter:
        query = query.filter(Livestock.health_status == health_filter)
    if status_filter:
        query = query.filter(Livestock.production_status == status_filter)
    
    livestock = query.order_by(Livestock.tag_number).all()
    categories = LivestockCategory.query.all()
    
    # Summary statistics
    total_count = Livestock.query.filter_by(is_active=True).count()
    healthy_count = Livestock.query.filter_by(health_status='Healthy', is_active=True).count()
    sick_count = Livestock.query.filter_by(health_status='Sick', is_active=True).count()
    pregnant_count = Livestock.query.filter_by(pregnancy_status='Pregnant', is_active=True).count()
    
    return render_template('livestock/list.html',
                         livestock=livestock,
                         categories=categories,
                         total_count=total_count,
                         healthy_count=healthy_count,
                         sick_count=sick_count,
                         pregnant_count=pregnant_count)

@app.route('/livestock/add', methods=['GET', 'POST'])
@login_required
def add_livestock():
    """Add new livestock"""
    if request.method == 'POST':
        tag_number = request.form.get('tag_number')
        
        # Check if tag already exists
        existing = Livestock.query.filter_by(tag_number=tag_number).first()
        if existing:
            flash('Tag number already exists!', 'danger')
            return redirect(url_for('add_livestock'))
        
        # Handle image upload
        image_file = request.files.get('image')
        image_url = None
        if image_file and allowed_image(image_file.filename):
            image_url = upload_to_cloudinary(image_file, 'livestock_photos')
        
        livestock = Livestock(
            tag_number=tag_number,
            name=request.form.get('name'),
            category_id=request.form.get('category_id'),
            breed=request.form.get('breed'),
            sex=request.form.get('sex'),
            date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d') if request.form.get('date_of_birth') else None,
            acquisition_date=datetime.strptime(request.form.get('acquisition_date'), '%Y-%m-%d') if request.form.get('acquisition_date') else date.today(),
            acquisition_type=request.form.get('acquisition_type'),
            acquisition_cost=request.form.get('acquisition_cost'),
            current_weight=request.form.get('current_weight'),
            color=request.form.get('color'),
            markings=request.form.get('markings'),
            dam_tag=request.form.get('dam_tag'),
            sire_tag=request.form.get('sire_tag'),
            location=request.form.get('location'),
            shed_number=request.form.get('shed_number'),
            notes=request.form.get('notes'),
            image_url=image_url,
            estimated_value=request.form.get('estimated_value')
        )
        
        db.session.add(livestock)
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_LIVESTOCK', 
                    f'Added livestock {tag_number}', 'Livestock')
        
        flash('Livestock added successfully!', 'success')
        return redirect(url_for('livestock_list'))
    
    categories = LivestockCategory.query.all()
    return render_template('livestock/add.html', categories=categories)

@app.route('/livestock/<int:livestock_id>')
@login_required
def livestock_detail(livestock_id):
    """View livestock details"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    # Get related records
    feeding_records = LivestockFeeding.query.filter_by(
        animal_id=livestock_id
    ).order_by(LivestockFeeding.feeding_time.desc()).limit(20).all()
    
    health_records = LivestockHealth.query.filter_by(
        animal_id=livestock_id
    ).order_by(LivestockHealth.performed_date.desc()).limit(20).all()
    
    breeding_records = BreedingRecord.query.filter_by(
        animal_id=livestock_id
    ).order_by(BreedingRecord.service_date.desc()).limit(10).all()
    
    production_records = LivestockProduction.query.filter_by(
        animal_id=livestock_id
    ).order_by(LivestockProduction.production_date.desc()).limit(20).all()
    
    weight_records = WeightRecord.query.filter_by(
        animal_id=livestock_id
    ).order_by(WeightRecord.weigh_date.desc()).limit(20).all()
    
    milk_records = MilkRecord.query.filter_by(
        animal_id=livestock_id
    ).order_by(MilkRecord.milking_date.desc()).limit(30).all()
    
    # Calculate statistics
    avg_milk = db.session.query(func.avg(MilkRecord.quantity_litres)).filter(
        MilkRecord.animal_id == livestock_id
    ).scalar() or 0
    
    weight_gain = calculate_weight_gain(livestock_id)
    
    return render_template('livestock/detail.html',
                         animal=animal,
                         feeding_records=feeding_records,
                         health_records=health_records,
                         breeding_records=breeding_records,
                         production_records=production_records,
                         weight_records=weight_records,
                         milk_records=milk_records,
                         avg_milk=avg_milk,
                         weight_gain=weight_gain)

@app.route('/livestock/<int:livestock_id>/feeding/add', methods=['GET', 'POST'])
@login_required
def add_feeding_record(livestock_id):
    """Add feeding record"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'feeding_photos')
        
        feeding = LivestockFeeding(
            animal_id=livestock_id,
            feed_type=request.form.get('feed_type'),
            feed_name=request.form.get('feed_name'),
            quantity_kg=request.form.get('quantity_kg'),
            feeding_time=datetime.strptime(request.form.get('feeding_time'), '%Y-%m-%dT%H:%M'),
            feeding_schedule=request.form.get('feeding_schedule'),
            fed_by=current_user.id,
            notes=request.form.get('notes'),
            photo_url=photo_url,
            cost=request.form.get('cost')
        )
        
        db.session.add(feeding)
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_FEEDING', 
                    f'Added feeding record for {animal.tag_number}', 'Livestock')
        
        flash('Feeding record added!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    return render_template('livestock/add_feeding.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/health/add', methods=['GET', 'POST'])
@login_required
def add_health_record(livestock_id):
    """Add health/veterinary record"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'health_photos')
        
        health = LivestockHealth(
            animal_id=livestock_id,
            record_type=request.form.get('record_type'),
            diagnosis=request.form.get('diagnosis'),
            treatment=request.form.get('treatment'),
            medication_used=request.form.get('medication_used'),
            dosage=request.form.get('dosage'),
            withdrawal_period_days=request.form.get('withdrawal_period_days'),
            veterinary_officer=request.form.get('veterinary_officer'),
            cost=request.form.get('cost'),
            next_action_date=datetime.strptime(request.form.get('next_action_date'), '%Y-%m-%d') if request.form.get('next_action_date') else None,
            next_action=request.form.get('next_action'),
            performed_by=current_user.id,
            performed_date=datetime.utcnow(),
            notes=request.form.get('notes'),
            photo_url=photo_url
        )
        
        # Update animal health status
        if request.form.get('update_health_status'):
            animal.health_status = request.form.get('health_status', animal.health_status)
        
        db.session.add(health)
        db.session.commit()
        
        # Create follow-up task if needed
        if request.form.get('next_action_date'):
            task = Task(
                task_title=f"Health Follow-up: {animal.tag_number}",
                task_description=f"Follow-up health check for {animal.tag_number}. Next action: {request.form.get('next_action')}",
                task_category='Livestock',
                task_type='Routine',
                priority='High',
                due_date=datetime.strptime(request.form.get('next_action_date'), '%Y-%m-%d'),
                livestock_id=livestock_id,
                assigned_to=current_user.id,
                reported_by=current_user.id
            )
            db.session.add(task)
            db.session.commit()
        
        log_activity(current_user.id, 'ADD_HEALTH_RECORD', 
                    f'Added health record for {animal.tag_number}', 'Livestock')
        
        flash('Health record added!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    return render_template('livestock/add_health.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/breeding/add', methods=['GET', 'POST'])
@login_required
def add_breeding_record(livestock_id):
    """Add breeding record"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        breeding = BreedingRecord(
            animal_id=livestock_id,
            record_type=request.form.get('record_type'),
            service_type=request.form.get('service_type'),
            service_date=datetime.strptime(request.form.get('service_date'), '%Y-%m-%d') if request.form.get('service_date') else None,
            bull_sire_id=request.form.get('bull_sire_id'),
            semen_batch=request.form.get('semen_batch'),
            technician=request.form.get('technician'),
            pregnancy_check_date=datetime.strptime(request.form.get('pregnancy_check_date'), '%Y-%m-%d') if request.form.get('pregnancy_check_date') else None,
            pregnancy_result=request.form.get('pregnancy_result'),
            expected_calving_date=datetime.strptime(request.form.get('expected_calving_date'), '%Y-%m-%d') if request.form.get('expected_calving_date') else None,
            actual_birth_date=datetime.strptime(request.form.get('actual_birth_date'), '%Y-%m-%d') if request.form.get('actual_birth_date') else None,
            offspring_count=request.form.get('offspring_count'),
            birth_weight_kg=request.form.get('birth_weight_kg'),
            complications=request.form.get('complications'),
            colostrum_fed=request.form.get('colostrum_fed') == 'on',
            weaning_date=datetime.strptime(request.form.get('weaning_date'), '%Y-%m-%d') if request.form.get('weaning_date') else None,
            recorded_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        # Update animal's pregnancy status
        if request.form.get('pregnancy_result') == 'Positive':
            animal.pregnancy_status = 'Pregnant'
        elif request.form.get('record_type') == 'Parturition':
            animal.pregnancy_status = 'Open'
        
        db.session.add(breeding)
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_BREEDING_RECORD', 
                    f'Added breeding record for {animal.tag_number}', 'Livestock')
        
        flash('Breeding record added!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    return render_template('livestock/add_breeding.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/production/add', methods=['GET', 'POST'])
@login_required
def add_production_record(livestock_id):
    """Add production record (milk, eggs, etc.)"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'production_photos')
        
        production = LivestockProduction(
            animal_id=livestock_id,
            product_type=request.form.get('product_type'),
            quantity=request.form.get('quantity'),
            unit=request.form.get('unit'),
            production_time=request.form.get('production_time'),
            production_date=datetime.strptime(request.form.get('production_date'), '%Y-%m-%d'),
            quality_grade=request.form.get('quality_grade'),
            value_ksh=request.form.get('value_ksh'),
            buyer=request.form.get('buyer'),
            recorded_by=current_user.id,
            notes=request.form.get('notes'),
            photo_url=photo_url
        )
        
        db.session.add(production)
        
        # If it's milk, add detailed milk record
        if request.form.get('product_type') == 'Milk':
            milk_record = MilkRecord(
                animal_id=livestock_id,
                milking_date=datetime.strptime(request.form.get('production_date'), '%Y-%m-%d'),
                milking_time=request.form.get('production_time'),
                quantity_litres=request.form.get('quantity'),
                butter_fat_content=request.form.get('butter_fat'),
                somatic_cell_count=request.form.get('somatic_cell_count'),
                milked_by=current_user.id,
                notes=request.form.get('notes')
            )
            db.session.add(milk_record)
        
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_PRODUCTION_RECORD', 
                    f'Added production record for {animal.tag_number}', 'Livestock')
        
        flash('Production record added!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    return render_template('livestock/add_production.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/weight/add', methods=['GET', 'POST'])
@login_required
def add_weight_record(livestock_id):
    """Add weight record"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        weight = WeightRecord(
            animal_id=livestock_id,
            weight_kg=request.form.get('weight_kg'),
            weigh_date=datetime.strptime(request.form.get('weigh_date'), '%Y-%m-%d'),
            weighed_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        # Update animal's current weight
        animal.current_weight = request.form.get('weight_kg')
        
        db.session.add(weight)
        db.session.commit()
        
        flash('Weight record added!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    return render_template('livestock/add_weight.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_livestock(livestock_id):
    """Edit livestock details"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        animal.name = request.form.get('name', animal.name)
        animal.breed = request.form.get('breed', animal.breed)
        animal.sex = request.form.get('sex', animal.sex)
        animal.color = request.form.get('color', animal.color)
        animal.location = request.form.get('location', animal.location)
        animal.shed_number = request.form.get('shed_number', animal.shed_number)
        animal.notes = request.form.get('notes', animal.notes)
        animal.estimated_value = request.form.get('estimated_value', animal.estimated_value)
        
        # Handle image upload
        image_file = request.files.get('image')
        if image_file and allowed_image(image_file.filename):
            animal.image_url = upload_to_cloudinary(image_file, 'livestock_photos')
        
        db.session.commit()
        
        log_activity(current_user.id, 'EDIT_LIVESTOCK', 
                    f'Edited livestock {animal.tag_number}', 'Livestock')
        
        flash('Livestock updated successfully!', 'success')
        return redirect(url_for('livestock_detail', livestock_id=livestock_id))
    
    categories = LivestockCategory.query.all()
    return render_template('livestock/edit.html', animal=animal, categories=categories)

@app.route('/livestock/<int:livestock_id>/sell', methods=['GET', 'POST'])
@login_required
def sell_livestock(livestock_id):
    """Record livestock sale"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        receipt = request.files.get('receipt')
        receipt_url = None
        if receipt and allowed_file(receipt.filename):
            receipt_url = upload_to_cloudinary(receipt, 'sale_receipts')
        
        sale = LivestockSale(
            animal_id=livestock_id,
            sale_date=datetime.strptime(request.form.get('sale_date'), '%Y-%m-%d'),
            buyer_name=request.form.get('buyer_name'),
            buyer_contact=request.form.get('buyer_contact'),
            sale_price=request.form.get('sale_price'),
            weight_at_sale_kg=request.form.get('weight_at_sale_kg'),
            sale_reason=request.form.get('sale_reason'),
            payment_received=request.form.get('payment_received') == 'on',
            receipt_url=receipt_url,
            sold_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        # Update animal status
        animal.production_status = 'Sold'
        animal.is_active = False
        
        # Record income if payment received
        if request.form.get('payment_received') == 'on':
            income = FarmIncome(
                income_date=datetime.strptime(request.form.get('sale_date'), '%Y-%m-%d'),
                income_source='Livestock Sales',
                income_category='Livestock',
                description=f"Sale of {animal.tag_number} - {animal.category.name}",
                total_amount=request.form.get('sale_price'),
                buyer_name=request.form.get('buyer_name'),
                buyer_contact=request.form.get('buyer_contact'),
                payment_method=request.form.get('payment_method', 'Cash'),
                payment_status='Paid',
                recorded_by=current_user.id
            )
            db.session.add(income)
        
        db.session.add(sale)
        db.session.commit()
        
        log_activity(current_user.id, 'SELL_LIVESTOCK', 
                    f'Sold livestock {animal.tag_number} for Ksh {request.form.get("sale_price")}', 'Livestock')
        
        flash('Livestock sale recorded!', 'success')
        return redirect(url_for('livestock_list'))
    
    return render_template('livestock/sell.html', animal=animal)

@app.route('/livestock/<int:livestock_id>/death', methods=['GET', 'POST'])
@login_required
def record_death(livestock_id):
    """Record livestock death"""
    animal = Livestock.query.get_or_404(livestock_id)
    
    if request.method == 'POST':
        death = LivestockDeath(
            animal_id=livestock_id,
            death_date=datetime.strptime(request.form.get('death_date'), '%Y-%m-%d'),
            cause_of_death=request.form.get('cause_of_death'),
            post_mortem_findings=request.form.get('post_mortem_findings'),
            disposal_method=request.form.get('disposal_method'),
            value_at_death=request.form.get('value_at_death'),
            reported_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        animal.production_status = 'Dead'
        animal.is_active = False
        
        db.session.add(death)
        db.session.commit()
        
        log_activity(current_user.id, 'RECORD_DEATH', 
                    f'Recorded death of {animal.tag_number}', 'Livestock')
        
        flash('Death recorded!', 'warning')
        return redirect(url_for('livestock_list'))
    
    return render_template('livestock/death.html', animal=animal)

# ============================================================================
# CROP MANAGEMENT ROUTES
# ============================================================================

@app.route('/crops')
@login_required
def crop_list():
    """List all crop plantings"""
    status_filter = request.args.get('status', 'Active')
    
    plantings = CropPlanting.query.filter_by(status=status_filter).order_by(
        CropPlanting.planting_date.desc()
    ).all()
    
    fields = FarmField.query.all()
    
    # Statistics
    total_plantings = CropPlanting.query.filter_by(status='Active').count()
    total_harvested = CropPlanting.query.filter_by(status='Harvested').count()
    total_area = db.session.query(func.sum(CropPlanting.area_planted)).filter_by(status='Active').scalar() or 0
    
    return render_template('crops/list.html',
                         plantings=plantings,
                         fields=fields,
                         total_plantings=total_plantings,
                         total_harvested=total_harvested,
                         total_area=total_area)

@app.route('/crops/planting/add', methods=['GET', 'POST'])
@login_required
def add_planting():
    """Add new crop planting"""
    if request.method == 'POST':
        planting = CropPlanting(
            crop_id=request.form.get('crop_id'),
            field_id=request.form.get('field_id'),
            planting_date=datetime.strptime(request.form.get('planting_date'), '%Y-%m-%d'),
            planting_method=request.form.get('planting_method'),
            seed_rate_used=request.form.get('seed_rate_used'),
            area_planted=request.form.get('area_planted'),
            seed_cost=request.form.get('seed_cost'),
            expected_harvest_date=datetime.strptime(request.form.get('expected_harvest_date'), '%Y-%m-%d') if request.form.get('expected_harvest_date') else None,
            planted_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        db.session.add(planting)
        
        # Record seed usage as expense
        if request.form.get('seed_cost') and float(request.form.get('seed_cost')) > 0:
            crop = Crop.query.get(request.form.get('crop_id'))
            field = FarmField.query.get(request.form.get('field_id'))
            expense = FarmExpense(
                expense_date=datetime.strptime(request.form.get('planting_date'), '%Y-%m-%d'),
                expense_category='Seeds',
                description=f"Seeds for {crop.name} planting in {field.field_name if field else 'Field'}",
                total_amount=request.form.get('seed_cost'),
                recorded_by=current_user.id
            )
            db.session.add(expense)
        
        # Update field status
        field = FarmField.query.get(request.form.get('field_id'))
        if field:
            field.current_status = 'Planted'
        
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_PLANTING', 
                    f'Added planting of crop in field', 'Crops')
        
        flash('Crop planting recorded!', 'success')
        return redirect(url_for('crop_list'))
    
    crops = Crop.query.order_by(Crop.name).all()
    fields = FarmField.query.filter(FarmField.current_status.in_(['Fallow', 'Under Preparation'])).all()
    return render_template('crops/add_planting.html', crops=crops, fields=fields)

@app.route('/crops/planting/<int:planting_id>')
@login_required
def planting_detail(planting_id):
    """View planting details"""
    planting = CropPlanting.query.get_or_404(planting_id)
    
    activities = CropActivity.query.filter_by(
        planting_id=planting_id
    ).order_by(CropActivity.activity_date.desc()).all()
    
    pest_controls = PestControl.query.filter_by(
        planting_id=planting_id
    ).order_by(PestControl.application_date.desc()).all()
    
    fertilizer_apps = FertilizerApplication.query.filter_by(
        planting_id=planting_id
    ).order_by(FertilizerApplication.application_date.desc()).all()
    
    harvests = Harvest.query.filter_by(
        planting_id=planting_id
    ).order_by(Harvest.harvest_date.desc()).all()
    
    # Total costs
    total_cost = db.session.query(func.sum(CropActivity.cost_incurred)).filter_by(
        planting_id=planting_id
    ).scalar() or 0
    
    total_fertilizer_cost = db.session.query(func.sum(FertilizerApplication.cost)).filter_by(
        planting_id=planting_id
    ).scalar() or 0
    
    total_pest_control_cost = db.session.query(func.sum(PestControl.cost)).filter_by(
        planting_id=planting_id
    ).scalar() or 0
    
    total_harvest_value = db.session.query(func.sum(Harvest.quantity_kg)).filter_by(
        planting_id=planting_id
    ).scalar() or 0
    
    return render_template('crops/planting_detail.html',
                         planting=planting,
                         activities=activities,
                         pest_controls=pest_controls,
                         fertilizer_apps=fertilizer_apps,
                         harvests=harvests,
                         total_cost=float(total_cost) + float(total_fertilizer_cost) + float(total_pest_control_cost),
                         total_harvest_value=total_harvest_value)

@app.route('/crops/activity/add/<int:planting_id>', methods=['GET', 'POST'])
@login_required
def add_crop_activity(planting_id):
    """Add crop activity record"""
    planting = CropPlanting.query.get_or_404(planting_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'crop_activities')
        
        activity = CropActivity(
            planting_id=planting_id,
            activity_type=request.form.get('activity_type'),
            activity_name=request.form.get('activity_name'),
            activity_date=datetime.strptime(request.form.get('activity_date'), '%Y-%m-%dT%H:%M'),
            duration_hours=request.form.get('duration_hours'),
            workers_involved=request.form.get('workers_involved'),
            cost_incurred=request.form.get('cost_incurred'),
            tools_used=request.form.get('tools_used'),
            inputs_used=request.form.get('inputs_used'),
            performed_by=current_user.id,
            notes=request.form.get('notes'),
            photo_url=photo_url,
            weather_conditions=request.form.get('weather_conditions')
        )
        
        db.session.add(activity)
        db.session.commit()
        
        flash('Crop activity recorded!', 'success')
        return redirect(url_for('planting_detail', planting_id=planting_id))
    
    # Activity types based on 8-4-4 syllabus
    activity_types = [
        'Land Preparation', 'Ploughing', 'Harrowing', 'Ridging',
        'Planting', 'Transplanting', 'Gap Filling',
        'Weeding', 'Mulching', 'Herbicide Application',
        'Fertilizer Application', 'Top-dressing', 'Foliar Feeding',
        'Irrigation', 'Pruning', 'Training', 'Staking',
        'Pest Scouting', 'Disease Inspection',
        'Harvesting', 'Threshing', 'Winnowing',
        'Soil Conservation', 'Other'
    ]
    
    return render_template('crops/add_activity.html', 
                         planting=planting,
                         activity_types=activity_types)

@app.route('/crops/harvest/add/<int:planting_id>', methods=['GET', 'POST'])
@login_required
def add_harvest(planting_id):
    """Add harvest record"""
    planting = CropPlanting.query.get_or_404(planting_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'harvest_photos')
        
        harvest = Harvest(
            planting_id=planting_id,
            harvest_date=datetime.strptime(request.form.get('harvest_date'), '%Y-%m-%d'),
            quantity_kg=request.form.get('quantity_kg'),
            quality_grade=request.form.get('quality_grade'),
            moisture_content=request.form.get('moisture_content'),
            harvesting_method=request.form.get('harvesting_method'),
            workers_involved=request.form.get('workers_involved'),
            labor_cost=request.form.get('labor_cost'),
            harvested_by=current_user.id,
            storage_location=request.form.get('storage_location'),
            notes=request.form.get('notes'),
            photo_url=photo_url
        )
        
        db.session.add(harvest)
        
        # Update planting status
        planting.actual_harvest_date = datetime.strptime(request.form.get('harvest_date'), '%Y-%m-%d')
        planting.actual_yield_kg = request.form.get('quantity_kg')
        
        if request.form.get('final_harvest') == 'on':
            planting.status = 'Harvested'
            # Update field status
            field = FarmField.query.get(planting.field_id)
            if field:
                field.current_status = 'Fallow'
        
        db.session.commit()
        
        flash('Harvest recorded!', 'success')
        return redirect(url_for('planting_detail', planting_id=planting_id))
    
    return render_template('crops/add_harvest.html', planting=planting)

@app.route('/crops/fertilizer/add/<int:planting_id>', methods=['GET', 'POST'])
@login_required
def add_fertilizer_application(planting_id):
    """Add fertilizer application record"""
    planting = CropPlanting.query.get_or_404(planting_id)
    
    if request.method == 'POST':
        fertilizer = FertilizerApplication(
            planting_id=planting_id,
            fertilizer_type=request.form.get('fertilizer_type'),
            application_type=request.form.get('application_type'),
            quantity_kg=request.form.get('quantity_kg'),
            application_date=datetime.strptime(request.form.get('application_date'), '%Y-%m-%dT%H:%M'),
            application_method=request.form.get('application_method'),
            cost=request.form.get('cost'),
            applied_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        db.session.add(fertilizer)
        
        # Record as expense
        if request.form.get('cost') and float(request.form.get('cost')) > 0:
            expense = FarmExpense(
                expense_date=datetime.strptime(request.form.get('application_date'), '%Y-%m-%dT%H:%M'),
                expense_category='Fertilizer',
                description=f"{request.form.get('fertilizer_type')} application for {planting.crop.name}",
                total_amount=request.form.get('cost'),
                recorded_by=current_user.id
            )
            db.session.add(expense)
        
        db.session.commit()
        
        flash('Fertilizer application recorded!', 'success')
        return redirect(url_for('planting_detail', planting_id=planting_id))
    
    return render_template('crops/add_fertilizer.html', planting=planting)

@app.route('/crops/pest-control/add/<int:planting_id>', methods=['GET', 'POST'])
@login_required
def add_pest_control(planting_id):
    """Add pest control record"""
    planting = CropPlanting.query.get_or_404(planting_id)
    
    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_url = None
        if photo and allowed_image(photo.filename):
            photo_url = upload_to_cloudinary(photo, 'pest_control')
        
        pest_control = PestControl(
            planting_id=planting_id,
            control_type=request.form.get('control_type'),
            pest_or_disease=request.form.get('pest_or_disease'),
            chemical_used=request.form.get('chemical_used'),
            application_rate=request.form.get('application_rate'),
            application_method=request.form.get('application_method'),
            application_date=datetime.strptime(request.form.get('application_date'), '%Y-%m-%dT%H:%M'),
            weather_conditions=request.form.get('weather_conditions'),
            safety_measures=request.form.get('safety_measures'),
            re_entry_period_hours=request.form.get('re_entry_period_hours'),
            harvest_interval_days=request.form.get('harvest_interval_days'),
            cost=request.form.get('cost'),
            effectiveness=request.form.get('effectiveness'),
            performed_by=current_user.id,
            notes=request.form.get('notes'),
            photo_url=photo_url
        )
        
        db.session.add(pest_control)
        
        # Record as expense
        if request.form.get('cost') and float(request.form.get('cost')) > 0:
            expense = FarmExpense(
                expense_date=datetime.strptime(request.form.get('application_date'), '%Y-%m-%dT%H:%M'),
                expense_category='Chemicals',
                description=f"Pest control for {planting.crop.name}: {request.form.get('pest_or_disease')}",
                total_amount=request.form.get('cost'),
                recorded_by=current_user.id
            )
            db.session.add(expense)
        
        db.session.commit()
        
        flash('Pest control record added!', 'success')
        return redirect(url_for('planting_detail', planting_id=planting_id))
    
    return render_template('crops/add_pest_control.html', planting=planting)

@app.route('/crops/fields')
@login_required
def field_list():
    """List all farm fields"""
    fields = FarmField.query.all()
    return render_template('crops/fields.html', fields=fields)

@app.route('/crops/fields/add', methods=['GET', 'POST'])
@login_required
def add_field():
    """Add new farm field"""
    if request.method == 'POST':
        field = FarmField(
            field_name=request.form.get('field_name'),
            field_code=request.form.get('field_code'),
            size_acres=request.form.get('size_acres'),
            soil_type=request.form.get('soil_type'),
            ph_level=request.form.get('ph_level'),
            drainage=request.form.get('drainage'),
            location_description=request.form.get('location_description'),
            latitude=request.form.get('latitude'),
            longitude=request.form.get('longitude'),
            description=request.form.get('description')
        )
        
        db.session.add(field)
        db.session.commit()
        
        flash('Field added!', 'success')
        return redirect(url_for('field_list'))
    
    return render_template('crops/add_field.html')

@app.route('/crops/produce-sale/add', methods=['GET', 'POST'])
@login_required
def add_produce_sale():
    """Add produce sale record"""
    if request.method == 'POST':
        sale = ProduceSale(
            harvest_id=request.form.get('harvest_id') if request.form.get('harvest_id') else None,
            sale_date=datetime.strptime(request.form.get('sale_date'), '%Y-%m-%d'),
            produce_type=request.form.get('produce_type'),
            quantity_sold_kg=request.form.get('quantity_sold_kg'),
            unit_price_ksh=request.form.get('unit_price_ksh'),
            total_amount=request.form.get('total_amount'),
            buyer_name=request.form.get('buyer_name'),
            buyer_contact=request.form.get('buyer_contact'),
            payment_status=request.form.get('payment_status', 'Pending'),
            payment_method=request.form.get('payment_method'),
            sold_by=current_user.id,
            notes=request.form.get('notes')
        )
        
        db.session.add(sale)
        
        # Record income
        income = FarmIncome(
            income_date=datetime.strptime(request.form.get('sale_date'), '%Y-%m-%d'),
            income_source='Crop Sales',
            income_category='Crops',
            description=f"Sale of {request.form.get('produce_type')} - {request.form.get('quantity_sold_kg')} kg",
            quantity=request.form.get('quantity_sold_kg'),
            unit_price=request.form.get('unit_price_ksh'),
            total_amount=request.form.get('total_amount'),
            buyer_name=request.form.get('buyer_name'),
            buyer_contact=request.form.get('buyer_contact'),
            payment_method=request.form.get('payment_method'),
            payment_status=request.form.get('payment_status', 'Pending'),
            recorded_by=current_user.id
        )
        db.session.add(income)
        
        db.session.commit()
        
        flash('Produce sale recorded!', 'success')
        return redirect(url_for('crop_list'))
    
    harvests = Harvest.query.order_by(Harvest.harvest_date.desc()).all()
    return render_template('crops/add_sale.html', harvests=harvests)

# ============================================================================
# TASK MANAGEMENT ROUTES
# ============================================================================

@app.route('/tasks')
@login_required
def task_list():
    """List all tasks"""
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    category_filter = request.args.get('category')
    assigned_filter = request.args.get('assigned_to')
    
    query = Task.query
    
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)
    if category_filter:
        query = query.filter(Task.task_category == category_filter)
    if assigned_filter:
        query = query.filter(Task.assigned_to == assigned_filter)
    
    tasks = query.order_by(Task.due_date.asc()).all()
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('tasks/list.html', tasks=tasks, users=users)

@app.route('/tasks/add', methods=['GET', 'POST'])
@login_required
def add_task():
    """Add new task"""
    if request.method == 'POST':
        task = Task(
            task_title=request.form.get('task_title'),
            task_description=request.form.get('task_description'),
            task_category=request.form.get('task_category'),
            task_type=request.form.get('task_type'),
            priority=request.form.get('priority', 'Medium'),
            assigned_to=request.form.get('assigned_to') if request.form.get('assigned_to') else None,
            assigned_by=current_user.id,
            reported_by=current_user.id,
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d') if request.form.get('due_date') else None,
            estimated_hours=request.form.get('estimated_hours'),
            location=request.form.get('location'),
            tools_required=request.form.get('tools_required'),
            livestock_id=request.form.get('livestock_id') if request.form.get('livestock_id') else None,
            planting_id=request.form.get('planting_id') if request.form.get('planting_id') else None,
            field_id=request.form.get('field_id') if request.form.get('field_id') else None
        )
        
        db.session.add(task)
        
        # Create notification for assigned user
        if request.form.get('assigned_to'):
            notification = Notification(
                user_id=request.form.get('assigned_to'),
                title='New Task Assigned',
                message=f"You have been assigned a new task: {task.task_title}",
                notification_type='info',
                link=url_for('task_detail', task_id=task.id)
            )
            db.session.add(notification)
        
        db.session.commit()
        
        log_activity(current_user.id, 'CREATE_TASK', 
                    f'Created task: {task.task_title}', 'Tasks')
        
        flash('Task created!', 'success')
        return redirect(url_for('task_list'))
    
    users = User.query.filter_by(is_active=True).all()
    livestock = Livestock.query.filter_by(is_active=True).all()
    plantings = CropPlanting.query.filter_by(status='Active').all()
    fields = FarmField.query.all()
    
    return render_template('tasks/add.html',
                         users=users,
                         livestock=livestock,
                         plantings=plantings,
                         fields=fields)

@app.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    """View task details"""
    task = Task.query.get_or_404(task_id)
    comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at).all()
    
    return render_template('tasks/detail.html', task=task, comments=comments)

@app.route('/tasks/<int:task_id>/start', methods=['POST'])
@login_required
def start_task(task_id):
    """Mark task as in progress"""
    task = Task.query.get_or_404(task_id)
    task.status = 'In Progress'
    task.start_date = datetime.utcnow()
    db.session.commit()
    
    flash('Task started!', 'info')
    return redirect(url_for('task_detail', task_id=task_id))

@app.route('/tasks/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    """Mark task as complete"""
    task = Task.query.get_or_404(task_id)
    
    photo = request.files.get('completion_photo')
    photo_url = None
    if photo and allowed_image(photo.filename):
        photo_url = upload_to_cloudinary(photo, 'task_completion')
    
    task.status = 'Completed'
    task.completed_by = current_user.id
    task.completion_date = datetime.utcnow()
    task.completion_notes = request.form.get('completion_notes')
    task.completion_photo_url = photo_url
    task.actual_hours = request.form.get('actual_hours')
    
    db.session.commit()
    
    log_activity(current_user.id, 'COMPLETE_TASK', 
                f'Completed task: {task.task_title}', 'Tasks')
    
    flash('Task marked as complete!', 'success')
    return redirect(url_for('task_list'))

@app.route('/tasks/<int:task_id>/comment', methods=['POST'])
@login_required
def add_task_comment(task_id):
    """Add comment to task"""
    task = Task.query.get_or_404(task_id)
    
    photo = request.files.get('photo')
    photo_url = None
    if photo and allowed_image(photo.filename):
        photo_url = upload_to_cloudinary(photo, 'task_comments')
    
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        comment=request.form.get('comment'),
        photo_url=photo_url
    )
    
    db.session.add(comment)
    db.session.commit()
    
    flash('Comment added!', 'success')
    return redirect(url_for('task_detail', task_id=task_id))

# ============================================================================
# ATTENDANCE ROUTES
# ============================================================================

@app.route('/attendance')
@login_required
def attendance_list():
    """View attendance records"""
    user_id = request.args.get('user_id', current_user.id, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    attendances = Attendance.query.filter(
        Attendance.user_id == user_id,
        extract('month', Attendance.attendance_date) == month,
        extract('year', Attendance.attendance_date) == year
    ).order_by(Attendance.attendance_date.desc()).all()
    
    # Calculate statistics
    present_days = sum(1 for a in attendances if a.status == 'Present')
    absent_days = sum(1 for a in attendances if a.status == 'Absent')
    late_days = sum(1 for a in attendances if a.status == 'Late')
    
    # Get days in month
    days_in_month = calendar.monthrange(year, month)[1]
    unrecorded_days = days_in_month - len(attendances)
    
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('attendance/list.html',
                         attendances=attendances,
                         present_days=present_days,
                         absent_days=absent_days,
                         late_days=late_days,
                         unrecorded_days=unrecorded_days,
                         users=users,
                         selected_user=user_id,
                         month=month,
                         year=year)

@app.route('/attendance/check-in', methods=['POST'])
@login_required
def check_in():
    """Employee check-in"""
    today = date.today()
    
    # Check if already checked in today
    existing = Attendance.query.filter_by(
        user_id=current_user.id,
        attendance_date=today
    ).first()
    
    if existing:
        flash('You have already checked in today.', 'warning')
        return redirect(url_for('worker_dashboard'))
    
    attendance = Attendance(
        user_id=current_user.id,
        attendance_date=today,
        time_in=datetime.utcnow(),
        status='Present',
        check_in_method='Manual',
        check_in_location=request.form.get('location', 'Farm'),
        notes=request.form.get('notes')
    )
    
    db.session.add(attendance)
    db.session.commit()
    
    log_activity(current_user.id, 'CHECK_IN', 'Employee checked in', 'Attendance')
    
    flash('Check-in successful!', 'success')
    return redirect(url_for('worker_dashboard'))

@app.route('/attendance/check-out', methods=['POST'])
@login_required
def check_out():
    """Employee check-out"""
    today = date.today()
    
    attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        attendance_date=today
    ).first()
    
    if not attendance:
        flash('You need to check in first.', 'danger')
        return redirect(url_for('worker_dashboard'))
    
    if attendance.time_out:
        flash('You have already checked out today.', 'warning')
        return redirect(url_for('worker_dashboard'))
    
    attendance.time_out = datetime.utcnow()
    
    # Calculate hours worked
    if attendance.time_in:
        delta = attendance.time_out - attendance.time_in
        attendance.hours_worked = round(delta.total_seconds() / 3600, 2)
    
    db.session.commit()
    
    log_activity(current_user.id, 'CHECK_OUT', 'Employee checked out', 'Attendance')
    
    flash('Check-out successful!', 'success')
    return redirect(url_for('worker_dashboard'))

@app.route('/attendance/report')
@login_required
@admin_required
def attendance_report():
    """Generate attendance report"""
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    department = request.args.get('department')
    
    query = db.session.query(
        User.id,
        User.first_name,
        User.last_name,
        User.department,
        func.count(case([(Attendance.status == 'Present', 1)])).label('present_days'),
        func.count(case([(Attendance.status == 'Absent', 1)])).label('absent_days'),
        func.count(case([(Attendance.status == 'Late', 1)])).label('late_days'),
        func.sum(Attendance.hours_worked).label('total_hours')
    ).outerjoin(Attendance, and_(
        Attendance.user_id == User.id,
        extract('month', Attendance.attendance_date) == month,
        extract('year', Attendance.attendance_date) == year
    ))
    
    if department:
        query = query.filter(User.department == department)
    
    report = query.group_by(User.id).all()
    
    departments = db.session.query(User.department).distinct().all()
    
    return render_template('attendance/report.html', 
                         report=report, 
                         month=month, 
                         year=year,
                         departments=[d[0] for d in departments if d[0]])

# ============================================================================
# FINANCIAL MANAGEMENT ROUTES
# ============================================================================

@app.route('/finance')
@login_required
@admin_required
def finance_dashboard():
    """Financial dashboard"""
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Monthly summary
    monthly_income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
        extract('month', FarmIncome.income_date) == current_month,
        extract('year', FarmIncome.income_date) == current_year
    ).scalar() or 0
    
    monthly_expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
        extract('month', FarmExpense.expense_date) == current_month,
        extract('year', FarmExpense.expense_date) == current_year
    ).scalar() or 0
    
    # Year to date
    ytd_income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
        extract('year', FarmIncome.income_date) == current_year
    ).scalar() or 0
    
    ytd_expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
        extract('year', FarmExpense.expense_date) == current_year
    ).scalar() or 0
    
    # Expense breakdown
    expense_categories = db.session.query(
        FarmExpense.expense_category,
        func.sum(FarmExpense.total_amount)
    ).filter(
        extract('month', FarmExpense.expense_date) == current_month,
        extract('year', FarmExpense.expense_date) == current_year
    ).group_by(FarmExpense.expense_category).all()
    
    # Income sources
    income_sources = db.session.query(
        FarmIncome.income_source,
        func.sum(FarmIncome.total_amount)
    ).filter(
        extract('month', FarmIncome.income_date) == current_month,
        extract('year', FarmIncome.income_date) == current_year
    ).group_by(FarmIncome.income_source).all()
    
    # Pending payments
    pending_expenses = FarmExpense.query.filter_by(payment_status='Pending').count()
    pending_income = FarmIncome.query.filter_by(payment_status='Pending').count()
    
    # Cash flow (last 6 months)
    cash_flow = []
    for i in range(5, -1, -1):
        month_date = date.today().replace(day=1) - timedelta(days=i*30)
        income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
            extract('month', FarmIncome.income_date) == month_date.month,
            extract('year', FarmIncome.income_date) == month_date.year
        ).scalar() or 0
        
        expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
            extract('month', FarmExpense.expense_date) == month_date.month,
            extract('year', FarmExpense.expense_date) == month_date.year
        ).scalar() or 0
        
        cash_flow.append({
            'month': month_date.strftime('%b %Y'),
            'income': float(income),
            'expenses': float(expenses),
            'net': float(income) - float(expenses)
        })
    
    return render_template('finance/dashboard.html',
                         monthly_income=monthly_income,
                         monthly_expenses=monthly_expenses,
                         ytd_income=ytd_income,
                         ytd_expenses=ytd_expenses,
                         expense_categories=expense_categories,
                         income_sources=income_sources,
                         pending_expenses=pending_expenses,
                         pending_income=pending_income,
                         cash_flow=cash_flow,
                         net_income=float(monthly_income) - float(monthly_expenses))

@app.route('/finance/income')
@login_required
def income_list():
    """List all income records"""
    page = request.args.get('page', 1, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    query = FarmIncome.query.filter(
        extract('month', FarmIncome.income_date) == month,
        extract('year', FarmIncome.income_date) == year
    )
    
    incomes = query.order_by(FarmIncome.income_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    total_income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
        extract('month', FarmIncome.income_date) == month,
        extract('year', FarmIncome.income_date) == year
    ).scalar() or 0
    
    return render_template('finance/income.html', 
                         incomes=incomes, 
                         total_income=total_income,
                         month=month,
                         year=year)

@app.route('/finance/income/add', methods=['POST'])
@login_required
def add_income():
    """Add income record"""
    if request.method == 'POST':
        receipt = request.files.get('receipt')
        receipt_url = None
        if receipt and allowed_file(receipt.filename):
            receipt_url = upload_to_cloudinary(receipt, 'income_receipts')
        
        income = FarmIncome(
            income_date=datetime.strptime(request.form.get('income_date'), '%Y-%m-%d'),
            income_source=request.form.get('income_source'),
            income_category=request.form.get('income_category'),
            description=request.form.get('description'),
            quantity=request.form.get('quantity'),
            unit_price=request.form.get('unit_price'),
            total_amount=request.form.get('total_amount'),
            buyer_name=request.form.get('buyer_name'),
            buyer_contact=request.form.get('buyer_contact'),
            payment_method=request.form.get('payment_method'),
            payment_status=request.form.get('payment_status', 'Pending'),
            receipt_number=generate_reference_number('INC'),
            receipt_url=receipt_url,
            recorded_by=current_user.id
        )
        
        db.session.add(income)
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_INCOME', 
                    f'Added income of Ksh {request.form.get("total_amount")}', 'Finance')
        
        flash('Income recorded!', 'success')
    return redirect(url_for('income_list'))

@app.route('/finance/expenses')
@login_required
def expense_list():
    """List all expenses"""
    page = request.args.get('page', 1, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    query = FarmExpense.query.filter(
        extract('month', FarmExpense.expense_date) == month,
        extract('year', FarmExpense.expense_date) == year
    )
    
    expenses = query.order_by(FarmExpense.expense_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    total_expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
        extract('month', FarmExpense.expense_date) == month,
        extract('year', FarmExpense.expense_date) == year
    ).scalar() or 0
    
    expense_categories = [
        'Feed', 'Fertilizer', 'Chemicals', 'Seeds', 'Labour',
        'Veterinary Services', 'Fuel', 'Equipment Repair',
        'Transport', 'Utilities', 'Rent', 'Insurance',
        'Packaging', 'Marketing', 'Miscellaneous'
    ]
    
    return render_template('finance/expenses.html', 
                         expenses=expenses,
                         total_expenses=total_expenses,
                         expense_categories=expense_categories,
                         month=month,
                         year=year)

@app.route('/finance/expenses/add', methods=['POST'])
@login_required
def add_expense():
    """Add expense record"""
    if request.method == 'POST':
        receipt = request.files.get('receipt')
        receipt_url = None
        if receipt and allowed_file(receipt.filename):
            receipt_url = upload_to_cloudinary(receipt, 'expense_receipts')
        
        expense = FarmExpense(
            expense_date=datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d'),
            expense_category=request.form.get('expense_category'),
            description=request.form.get('description'),
            quantity=request.form.get('quantity'),
            unit_price=request.form.get('unit_price'),
            total_amount=request.form.get('total_amount'),
            supplier_name=request.form.get('supplier_name'),
            supplier_contact=request.form.get('supplier_contact'),
            payment_method=request.form.get('payment_method'),
            payment_status=request.form.get('payment_status', 'Pending'),
            receipt_url=receipt_url,
            recorded_by=current_user.id
        )
        
        db.session.add(expense)
        db.session.commit()
        
        log_activity(current_user.id, 'ADD_EXPENSE', 
                    f'Added expense of Ksh {request.form.get("total_amount")}', 'Finance')
        
        flash('Expense recorded!', 'success')
    return redirect(url_for('expense_list'))

@app.route('/finance/payroll')
@login_required
@admin_required
def payroll_list():
    """Payroll management"""
    period = request.args.get('period', datetime.now().strftime('%Y-%m'))
    
    payrolls = Payroll.query.filter_by(payroll_period=period).all()
    
    # Calculate totals
    total_gross = sum(float(p.gross_pay) for p in payrolls if p.gross_pay)
    total_net = sum(float(p.net_pay) for p in payrolls if p.net_pay)
    total_deductions = sum(float(p.total_deductions) for p in payrolls if p.total_deductions)
    
    return render_template('finance/payroll.html', 
                         payrolls=payrolls,
                         period=period,
                         total_gross=total_gross,
                         total_net=total_net,
                         total_deductions=total_deductions)

@app.route('/finance/payroll/generate', methods=['POST'])
@login_required
@admin_required
def generate_payroll():
    """Generate payroll for all employees"""
    period = request.form.get('period', datetime.now().strftime('%Y-%m'))
    
    # Check if already generated
    existing = Payroll.query.filter_by(payroll_period=period).first()
    if existing:
        flash(f'Payroll for {period} already exists!', 'warning')
        return redirect(url_for('payroll_list'))
    
    employees = User.query.filter_by(is_active=True).all()
    payroll_count = 0
    
    for emp in employees:
        if not emp.basic_salary or float(emp.basic_salary) == 0:
            continue
        
        gross = float(emp.basic_salary)
        
        # Calculate overtime for the month
        month_date = datetime.strptime(period, '%Y-%m')
        overtime_amount = db.session.query(func.sum(Overtime.amount)).filter(
            Overtime.user_id == emp.id,
            extract('month', Overtime.overtime_date) == month_date.month,
            extract('year', Overtime.overtime_date) == month_date.year,
            Overtime.status == 'Approved'
        ).scalar() or 0
        
        # Calculate bonuses
        bonus_amount = db.session.query(func.sum(Bonus.amount)).filter(
            Bonus.user_id == emp.id,
            extract('month', Bonus.bonus_date) == month_date.month,
            extract('year', Bonus.bonus_date) == month_date.year
        ).scalar() or 0
        
        gross += float(overtime_amount) + float(bonus_amount)
        
        # Calculate statutory deductions
        nssf = calculate_nssf(gross)
        nhif = calculate_nhif(gross)
        paye = calculate_kra_paye(gross)
        
        # Advance recovery
        advances = SalaryAdvance.query.filter_by(
            user_id=emp.id, 
            status='Active'
        ).all()
        advance_recovery = sum(float(adv.monthly_repayment) for adv in advances if adv.monthly_repayment)
        
        total_deductions = nssf + nhif + paye + advance_recovery
        net_pay = gross - total_deductions
        
        payroll = Payroll(
            payroll_period=period,
            user_id=emp.id,
            basic_salary=emp.basic_salary,
            allowances=0,
            overtime_amount=overtime_amount,
            bonuses=bonus_amount,
            gross_pay=gross,
            nssf_deduction=nssf,
            nhif_deduction=nhif,
            paye_tax=paye,
            advance_recovery=advance_recovery,
            total_deductions=total_deductions,
            net_pay=net_pay,
            generated_by=current_user.id
        )
        
        db.session.add(payroll)
        payroll_count += 1
    
    db.session.commit()
    
    log_activity(current_user.id, 'GENERATE_PAYROLL', 
                f'Generated payroll for period {period} ({payroll_count} employees)', 'Finance')
    
    flash(f'Payroll for {period} generated for {payroll_count} employees!', 'success')
    return redirect(url_for('payroll_list'))

@app.route('/finance/wages')
@login_required
def wage_list():
    """View wages"""
    user_id = request.args.get('user_id', type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    query = Wage.query.filter(
        extract('month', Wage.wage_date) == month,
        extract('year', Wage.wage_date) == year
    )
    
    if user_id:
        query = query.filter(Wage.user_id == user_id)
    
    wages = query.order_by(Wage.wage_date.desc()).all()
    users = User.query.filter_by(is_active=True).all()
    
    total_wages = sum(float(w.amount) for w in wages)
    
    return render_template('finance/wages.html',
                         wages=wages,
                         users=users,
                         total_wages=total_wages,
                         selected_user=user_id,
                         month=month,
                         year=year)

@app.route('/finance/wages/add', methods=['POST'])
@login_required
def add_wage():
    """Add daily/casual wage"""
    if request.method == 'POST':
        wage = Wage(
            user_id=request.form.get('user_id'),
            wage_date=datetime.strptime(request.form.get('wage_date'), '%Y-%m-%d'),
            wage_type=request.form.get('wage_type', 'Daily Rate'),
            hours_worked=request.form.get('hours_worked'),
            rate_per_hour=request.form.get('rate_per_hour'),
            task_description=request.form.get('task_description'),
            amount=request.form.get('amount'),
            payment_status=request.form.get('payment_status', 'Pending'),
            paid_by=current_user.id
        )
        
        db.session.add(wage)
        db.session.commit()
        
        flash('Wage recorded!', 'success')
    return redirect(url_for('wage_list'))

# ============================================================================
# LEAVE MANAGEMENT ROUTES
# ============================================================================

@app.route('/leaves')
@login_required
def leave_list():
    """View leave records"""
    if current_user.role in ['admin', 'manager']:
        leaves = Leave.query.order_by(Leave.start_date.desc()).all()
    else:
        leaves = Leave.query.filter_by(user_id=current_user.id).order_by(
            Leave.start_date.desc()
        ).all()
    
    return render_template('leaves/list.html', leaves=leaves)

@app.route('/leaves/apply', methods=['POST'])
@login_required
def apply_leave():
    """Apply for leave"""
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        days = (end_date - start_date).days + 1
        
        leave = Leave(
            user_id=current_user.id,
            leave_type=request.form.get('leave_type'),
            start_date=start_date,
            end_date=end_date,
            days_requested=days,
            reason=request.form.get('reason')
        )
        
        db.session.add(leave)
        db.session.commit()
        
        # Notify admin
        admins = User.query.filter(User.role.in_(['admin', 'manager'])).all()
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title='New Leave Request',
                message=f"{current_user.full_name} has applied for {days} days {request.form.get('leave_type')} leave",
                notification_type='info',
                link=url_for('leave_list')
            )
            db.session.add(notification)
        
        db.session.commit()
        
        flash('Leave application submitted!', 'success')
    return redirect(url_for('leave_list'))

@app.route('/leaves/<int:leave_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_leave(leave_id):
    """Approve leave request"""
    leave = Leave.query.get_or_404(leave_id)
    leave.status = 'Approved'
    leave.approved_by = current_user.id
    leave.approved_date = date.today()
    db.session.commit()
    
    flash('Leave approved!', 'success')
    return redirect(url_for('leave_list'))

@app.route('/leaves/<int:leave_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_leave(leave_id):
    """Reject leave request"""
    leave = Leave.query.get_or_404(leave_id)
    leave.status = 'Rejected'
    leave.approved_by = current_user.id
    leave.rejection_reason = request.form.get('reason')
    db.session.commit()
    
    flash('Leave rejected!', 'warning')
    return redirect(url_for('leave_list'))

# ============================================================================
# INVENTORY MANAGEMENT ROUTES
# ============================================================================

@app.route('/inventory')
@login_required
def inventory_list():
    """List inventory items"""
    category = request.args.get('category')
    
    query = InventoryItem.query
    if category:
        query = query.filter_by(item_category=category)
    
    items = query.order_by(InventoryItem.item_name).all()
    
    # Low stock alerts
    low_stock = InventoryItem.query.filter(
        InventoryItem.quantity_in_stock <= InventoryItem.reorder_level
    ).all()
    
    return render_template('inventory/list.html', 
                         items=items, 
                         low_stock=low_stock)

@app.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def add_inventory_item():
    """Add inventory item"""
    if request.method == 'POST':
        item = InventoryItem(
            item_code=request.form.get('item_code') or generate_reference_number('INV'),
            item_name=request.form.get('item_name'),
            item_category=request.form.get('item_category'),
            description=request.form.get('description'),
            unit_of_measure=request.form.get('unit_of_measure'),
            quantity_in_stock=request.form.get('quantity_in_stock', 0),
            reorder_level=request.form.get('reorder_level'),
            unit_price=request.form.get('unit_price'),
            supplier_name=request.form.get('supplier_name'),
            supplier_contact=request.form.get('supplier_contact'),
            storage_location=request.form.get('storage_location'),
            expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d') if request.form.get('expiry_date') else None,
            notes=request.form.get('notes')
        )
        
        # Calculate total value
        if item.quantity_in_stock and item.unit_price:
            item.total_value = float(item.quantity_in_stock) * float(item.unit_price)
        
        db.session.add(item)
        db.session.commit()
        
        flash('Inventory item added!', 'success')
        return redirect(url_for('inventory_list'))
    
    return render_template('inventory/add.html')

@app.route('/inventory/<int:item_id>/movement', methods=['POST'])
@login_required
def add_stock_movement(item_id):
    """Add stock movement"""
    item = InventoryItem.query.get_or_404(item_id)
    
    movement_type = request.form.get('movement_type')
    quantity = float(request.form.get('quantity'))
    
    movement = StockMovement(
        item_id=item_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_number=generate_reference_number('STK'),
        performed_by=current_user.id,
        reason=request.form.get('reason'),
        cost=request.form.get('cost')
    )
    
    # Update stock quantity
    if movement_type == 'In':
        item.quantity_in_stock = float(item.quantity_in_stock or 0) + quantity
    elif movement_type == 'Out':
        item.quantity_in_stock = float(item.quantity_in_stock or 0) - quantity
    elif movement_type == 'Adjustment':
        item.quantity_in_stock = quantity
    
    # Update total value
    if item.unit_price:
        item.total_value = float(item.quantity_in_stock) * float(item.unit_price)
    
    db.session.add(movement)
    db.session.commit()
    
    flash('Stock movement recorded!', 'success')
    return redirect(url_for('inventory_list'))

# ============================================================================
# FARM MAINTENANCE ROUTES
# ============================================================================

@app.route('/maintenance')
@login_required
def maintenance_overview():
    """Farm maintenance overview"""
    assets = FarmAsset.query.all()
    structures = FarmStructure.query.all()
    pending_maintenance = AssetMaintenance.query.filter(
        AssetMaintenance.next_maintenance_date <= date.today()
    ).all()
    
    return render_template('maintenance/overview.html',
                         assets=assets,
                         structures=structures,
                         pending_maintenance=pending_maintenance)

@app.route('/maintenance/assets/add', methods=['GET', 'POST'])
@login_required
def add_asset():
    """Add farm asset"""
    if request.method == 'POST':
        image = request.files.get('image')
        image_url = None
        if image and allowed_image(image.filename):
            image_url = upload_to_cloudinary(image, 'assets')
        
        asset = FarmAsset(
            asset_code=request.form.get('asset_code') or generate_reference_number('AST'),
            asset_name=request.form.get('asset_name'),
            asset_category=request.form.get('asset_category'),
            description=request.form.get('description'),
            purchase_date=datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d') if request.form.get('purchase_date') else None,
            purchase_price=request.form.get('purchase_price'),
            current_value=request.form.get('current_value'),
            useful_life_years=request.form.get('useful_life_years'),
            depreciation_rate=request.form.get('depreciation_rate'),
            location=request.form.get('location'),
            condition=request.form.get('condition', 'Good'),
            status=request.form.get('status', 'Active'),
            serial_number=request.form.get('serial_number'),
            manufacturer=request.form.get('manufacturer'),
            model=request.form.get('model'),
            image_url=image_url,
            notes=request.form.get('notes')
        )
        
        db.session.add(asset)
        db.session.commit()
        
        flash('Asset added!', 'success')
        return redirect(url_for('maintenance_overview'))
    
    return render_template('maintenance/add_asset.html')

@app.route('/maintenance/record/<int:asset_id>', methods=['POST'])
@login_required
def add_maintenance_record(asset_id):
    """Add maintenance record"""
    asset = FarmAsset.query.get_or_404(asset_id)
    
    receipt = request.files.get('receipt')
    receipt_url = None
    if receipt and allowed_file(receipt.filename):
        receipt_url = upload_to_cloudinary(receipt, 'maintenance_receipts')
    
    maintenance = AssetMaintenance(
        asset_id=asset_id,
        maintenance_date=datetime.strptime(request.form.get('maintenance_date'), '%Y-%m-%d'),
        maintenance_type=request.form.get('maintenance_type'),
        description=request.form.get('description'),
        cost=request.form.get('cost'),
        performed_by=request.form.get('performed_by'),
        service_provider=request.form.get('service_provider'),
        next_maintenance_date=datetime.strptime(request.form.get('next_maintenance_date'), '%Y-%m-%d') if request.form.get('next_maintenance_date') else None,
        parts_replaced=request.form.get('parts_replaced'),
        notes=request.form.get('notes'),
        receipt_url=receipt_url
    )
    
    # Update asset status if needed
    if request.form.get('update_status'):
        asset.status = request.form.get('status')
        asset.condition = request.form.get('condition')
    
    db.session.add(maintenance)
    db.session.commit()
    
    flash('Maintenance record added!', 'success')
    return redirect(url_for('maintenance_overview'))

# ============================================================================
# DAILY FARM LOG ROUTES
# ============================================================================

@app.route('/farm-log')
@login_required
def farm_log():
    """Daily farm log"""
    log_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    log_date = datetime.strptime(log_date, '%Y-%m-%d').date()
    
    daily_log = DailyFarmLog.query.filter_by(log_date=log_date).first()
    
    # Get today's activities
    today_tasks = Task.query.filter(
        Task.completion_date >= log_date,
        Task.completion_date < log_date + timedelta(days=1),
        Task.status == 'Completed'
    ).all()
    
    today_feeding = LivestockFeeding.query.filter(
        LivestockFeeding.feeding_time >= log_date,
        LivestockFeeding.feeding_time < log_date + timedelta(days=1)
    ).all()
    
    today_attendance = Attendance.query.filter_by(attendance_date=log_date).all()
    
    return render_template('farm_log.html',
                         daily_log=daily_log,
                         log_date=log_date,
                         today_tasks=today_tasks,
                         today_feeding=today_feeding,
                         today_attendance=today_attendance)

@app.route('/farm-log/save', methods=['POST'])
@login_required
def save_farm_log():
    """Save daily farm log"""
    log_date = datetime.strptime(request.form.get('log_date'), '%Y-%m-%d').date()
    
    daily_log = DailyFarmLog.query.filter_by(log_date=log_date).first()
    
    if not daily_log:
        daily_log = DailyFarmLog(log_date=log_date)
    
    daily_log.weather_conditions = request.form.get('weather_conditions')
    daily_log.temperature_min = request.form.get('temperature_min')
    daily_log.temperature_max = request.form.get('temperature_max')
    daily_log.rainfall_mm = request.form.get('rainfall_mm')
    daily_log.activities_summary = request.form.get('activities_summary')
    daily_log.issues_identified = request.form.get('issues_identified')
    daily_log.recommendations = request.form.get('recommendations')
    daily_log.recorded_by = current_user.id
    
    if not daily_log.id:
        db.session.add(daily_log)
    
    db.session.commit()
    
    flash('Farm log saved!', 'success')
    return redirect(url_for('farm_log', date=log_date.strftime('%Y-%m-%d')))

# ============================================================================
# REPORTING ROUTES
# ============================================================================

@app.route('/reports')
@login_required
def reports():
    """Reports dashboard"""
    return render_template('reports/index.html')

@app.route('/reports/livestock')
@login_required
def livestock_report():
    """Generate livestock report"""
    report_type = request.args.get('type', 'inventory')
    
    if report_type == 'inventory':
        livestock = Livestock.query.filter_by(is_active=True).order_by(
            Livestock.category_id, Livestock.tag_number
        ).all()
        
        category_summary = db.session.query(
            LivestockCategory.name,
            func.count(Livestock.id),
            func.sum(Livestock.estimated_value)
        ).join(Livestock).filter(Livestock.is_active==True).group_by(
            LivestockCategory.name
        ).all()
        
        return render_template('reports/livestock_inventory.html',
                             livestock=livestock,
                             category_summary=category_summary)
    
    elif report_type == 'health':
        health_summary = db.session.query(
            Livestock.health_status,
            func.count(Livestock.id)
        ).filter(Livestock.is_active==True).group_by(Livestock.health_status).all()
        
        recent_treatments = LivestockHealth.query.order_by(
            LivestockHealth.performed_date.desc()
        ).limit(50).all()
        
        return render_template('reports/livestock_health.html',
                             health_summary=health_summary,
                             recent_treatments=recent_treatments)
    
    elif report_type == 'production':
        milk_data = []
        for i in range(11, -1, -1):
            month_date = date.today().replace(day=1) - timedelta(days=i*30)
            total = db.session.query(func.sum(MilkRecord.quantity_litres)).filter(
                extract('month', MilkRecord.milking_date) == month_date.month,
                extract('year', MilkRecord.milking_date) == month_date.year
            ).scalar() or 0
            
            milk_data.append({
                'month': month_date.strftime('%b %Y'),
                'production': float(total)
            })
        
        return render_template('reports/livestock_production.html', milk_data=milk_data)
    
    return redirect(url_for('reports'))

@app.route('/reports/crops')
@login_required
def crop_report():
    """Generate crop report"""
    report_type = request.args.get('type', 'planting')
    
    if report_type == 'planting':
        plantings = CropPlanting.query.order_by(CropPlanting.planting_date.desc()).all()
        return render_template('reports/crop_plantings.html', plantings=plantings)
    
    elif report_type == 'harvest':
        harvests = Harvest.query.order_by(Harvest.harvest_date.desc()).all()
        total_harvested = db.session.query(func.sum(Harvest.quantity_kg)).scalar() or 0
        
        harvest_by_crop = db.session.query(
            Crop.name,
            func.sum(Harvest.quantity_kg)
        ).join(CropPlanting).join(Crop).group_by(Crop.name).all()
        
        return render_template('reports/crop_harvests.html',
                             harvests=harvests,
                             total_harvested=total_harvested,
                             harvest_by_crop=harvest_by_crop)
    
    return redirect(url_for('reports'))

@app.route('/reports/financial')
@login_required
@admin_required
def financial_report():
    """Generate financial report"""
    report_type = request.args.get('type', 'monthly')
    year = request.args.get('year', datetime.now().year, type=int)
    
    if report_type == 'monthly':
        monthly_data = []
        for month in range(1, 13):
            income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
                extract('month', FarmIncome.income_date) == month,
                extract('year', FarmIncome.income_date) == year
            ).scalar() or 0
            
            expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
                extract('month', FarmExpense.expense_date) == month,
                extract('year', FarmExpense.expense_date) == year
            ).scalar() or 0
            
            monthly_data.append({
                'month': calendar.month_name[month],
                'income': float(income),
                'expenses': float(expenses),
                'profit': float(income) - float(expenses)
            })
        
        total_income = sum(m['income'] for m in monthly_data)
        total_expenses = sum(m['expenses'] for m in monthly_data)
        total_profit = total_income - total_expenses
        
        return render_template('reports/financial_monthly.html',
                             monthly_data=monthly_data,
                             year=year,
                             total_income=total_income,
                             total_expenses=total_expenses,
                             total_profit=total_profit)
    
    elif report_type == 'expense_breakdown':
        expenses = db.session.query(
            FarmExpense.expense_category,
            func.sum(FarmExpense.total_amount).label('total')
        ).filter(
            extract('year', FarmExpense.expense_date) == year
        ).group_by(FarmExpense.expense_category).order_by(
            func.sum(FarmExpense.total_amount).desc()
        ).all()
        
        return render_template('reports/expense_breakdown.html', 
                             expenses=expenses, 
                             year=year)
    
    return redirect(url_for('reports'))

# ============================================================================
# CHART AND GRAPH API ENDPOINTS
# ============================================================================

@app.route('/api/charts/income-expense')
@login_required
def income_expense_chart():
    """Generate income vs expense chart data"""
    months = []
    income_data = []
    expense_data = []
    
    for i in range(11, -1, -1):
        month_date = date.today().replace(day=1) - timedelta(days=i*30)
        months.append(month_date.strftime('%b %Y'))
        
        income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
            extract('month', FarmIncome.income_date) == month_date.month,
            extract('year', FarmIncome.income_date) == month_date.year
        ).scalar() or 0
        
        expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
            extract('month', FarmExpense.expense_date) == month_date.month,
            extract('year', FarmExpense.expense_date) == month_date.year
        ).scalar() or 0
        
        income_data.append(float(income))
        expense_data.append(float(expenses))
    
    return jsonify({
        'labels': months,
        'income': income_data,
        'expenses': expense_data
    })

@app.route('/api/charts/livestock-distribution')
@login_required
def livestock_distribution_chart():
    """Generate livestock distribution chart data"""
    distribution = db.session.query(
        LivestockCategory.name,
        func.count(Livestock.id)
    ).join(Livestock).filter(Livestock.is_active==True).group_by(
        LivestockCategory.name
    ).all()
    
    return jsonify({
        'labels': [d[0] for d in distribution],
        'data': [d[1] for d in distribution]
    })

@app.route('/api/charts/milk-production')
@login_required
def milk_production_chart():
    """Generate milk production chart data"""
    milk_data = []
    
    for i in range(11, -1, -1):
        month_date = date.today().replace(day=1) - timedelta(days=i*30)
        total = db.session.query(func.sum(MilkRecord.quantity_litres)).filter(
            extract('month', MilkRecord.milking_date) == month_date.month,
            extract('year', MilkRecord.milking_date) == month_date.year
        ).scalar() or 0
        
        milk_data.append({
            'month': month_date.strftime('%b %Y'),
            'production': float(total)
        })
    
    return jsonify({
        'labels': [m['month'] for m in milk_data],
        'data': [m['production'] for m in milk_data]
    })

# ============================================================================
# PDF REPORT GENERATION
# ============================================================================

@app.route('/reports/generate-payslip/<int:payroll_id>')
@login_required
def generate_payslip(payroll_id):
    """Generate PDF payslip"""
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Check permission
    if current_user.role not in ['admin', 'manager'] and payroll.user_id != current_user.id:
        flash('You do not have permission to view this payslip.', 'danger')
        return redirect(url_for('dashboard'))
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    
    # Title
    elements.append(Paragraph(f"PAYSLIP - {payroll.payroll_period}", title_style))
    elements.append(Spacer(1, 20))
    
    # Employee details
    elements.append(Paragraph(f"<b>Employee:</b> {payroll.employee.full_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Employee ID:</b> {payroll.employee.employee_id}", styles['Normal']))
    elements.append(Paragraph(f"<b>Department:</b> {payroll.employee.department or 'N/A'}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Earnings table
    earnings_data = [
        ['EARNINGS', 'AMOUNT (Ksh)'],
        ['Basic Salary', f"{float(payroll.basic_salary):,.2f}"],
        ['Overtime', f"{float(payroll.overtime_amount):,.2f}"],
        ['Bonuses', f"{float(payroll.bonuses):,.2f}"],
        ['Gross Pay', f"{float(payroll.gross_pay):,.2f}"]
    ]
    
    t = Table(earnings_data, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Deductions table
    deductions_data = [
        ['DEDUCTIONS', 'AMOUNT (Ksh)'],
        ['NSSF', f"{float(payroll.nssf_deduction):,.2f}"],
        ['NHIF', f"{float(payroll.nhif_deduction):,.2f}"],
        ['PAYE Tax', f"{float(payroll.paye_tax):,.2f}"],
        ['Advance Recovery', f"{float(payroll.advance_recovery):,.2f}"],
        ['Total Deductions', f"{float(payroll.total_deductions):,.2f}"]
    ]
    
    t2 = Table(deductions_data, colWidths=[300, 150])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.red),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t2)
    elements.append(Spacer(1, 20))
    
    # Net pay
    elements.append(Paragraph(
        f"<b>NET PAY: Ksh {float(payroll.net_pay):,.2f}</b>",
        ParagraphStyle('NetPay', parent=styles['Normal'], fontSize=14, fontName='Helvetica-Bold')
    ))
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'payslip_{payroll.payroll_period}_{payroll.employee.last_name}.pdf'
    )

@app.route('/reports/generate-farm-report')
@login_required
@admin_required
def generate_farm_report():
    """Generate comprehensive farm report as PDF"""
    report_date = request.args.get('date', datetime.now().strftime('%Y-%m'))
    month = int(report_date.split('-')[1])
    year = int(report_date.split('-')[0])
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    elements.append(Paragraph(f"FARM MANAGEMENT REPORT - {report_date}", styles['Heading1']))
    elements.append(Spacer(1, 20))
    
    # Livestock Summary
    elements.append(Paragraph("LIVESTOCK SUMMARY", styles['Heading2']))
    
    livestock_data = [['Category', 'Count', 'Healthy', 'Sick', 'Value (Ksh)']]
    categories = LivestockCategory.query.all()
    
    for cat in categories:
        count = Livestock.query.filter_by(category_id=cat.id, is_active=True).count()
        healthy = Livestock.query.filter_by(category_id=cat.id, health_status='Healthy', is_active=True).count()
        sick = Livestock.query.filter_by(category_id=cat.id, health_status='Sick', is_active=True).count()
        value = db.session.query(func.sum(Livestock.estimated_value)).filter_by(
            category_id=cat.id, is_active=True
        ).scalar() or 0
        
        livestock_data.append([cat.name, str(count), str(healthy), str(sick), f"{float(value):,.2f}"])
    
    t = Table(livestock_data, colWidths=[100, 60, 60, 60, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Crop Summary
    elements.append(Paragraph("CROP SUMMARY", styles['Heading2']))
    
    crop_data = [['Crop', 'Field', 'Planted Area', 'Status', 'Expected Yield']]
    plantings = CropPlanting.query.filter_by(status='Active').all()
    
    for p in plantings[:20]:  # Limit to 20
        crop_data.append([
            p.crop.name,
            p.field.field_name,
            f"{float(p.area_planted):.2f} acres",
            p.current_stage or 'N/A',
            f"{float(p.expected_yield_kg):,.0f} kg" if p.expected_yield_kg else 'N/A'
        ])
    
    t2 = Table(crop_data, colWidths=[100, 80, 80, 80, 80])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t2)
    elements.append(Spacer(1, 20))
    
    # Financial Summary
    elements.append(Paragraph("FINANCIAL SUMMARY", styles['Heading2']))
    
    income = db.session.query(func.sum(FarmIncome.total_amount)).filter(
        extract('month', FarmIncome.income_date) == month,
        extract('year', FarmIncome.income_date) == year
    ).scalar() or 0
    
    expenses = db.session.query(func.sum(FarmExpense.total_amount)).filter(
        extract('month', FarmExpense.expense_date) == month,
        extract('year', FarmExpense.expense_date) == year
    ).scalar() or 0
    
    fin_data = [
        ['Description', 'Amount (Ksh)'],
        ['Total Income', f"{float(income):,.2f}"],
        ['Total Expenses', f"{float(expenses):,.2f}"],
        ['Net Profit/Loss', f"{float(income) - float(expenses):,.2f}"]
    ]
    
    t3 = Table(fin_data, colWidths=[250, 150])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t3)
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'farm_report_{report_date}.pdf'
    )

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_attendance_rate(user_id):
    """Calculate employee attendance rate for current month"""
    today = date.today()
    first_of_month = today.replace(day=1)
    
    total_working_days = 0
    current_date = first_of_month
    while current_date <= today:
        if current_date.weekday() < 6:  # Monday to Saturday
            total_working_days += 1
        current_date += timedelta(days=1)
    
    present_days = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.attendance_date >= first_of_month,
        Attendance.status.in_(['Present', 'Late'])
    ).count()
    
    if total_working_days > 0:
        return round((present_days / total_working_days) * 100, 1)
    return 0

def calculate_weight_gain(livestock_id):
    """Calculate average daily weight gain for livestock"""
    weights = WeightRecord.query.filter_by(
        animal_id=livestock_id
    ).order_by(WeightRecord.weigh_date.asc()).all()
    
    if len(weights) < 2:
        return 0
    
    first_weight = float(weights[0].weight_kg)
    last_weight = float(weights[-1].weight_kg)
    days_between = (weights[-1].weigh_date - weights[0].weigh_date).days
    
    if days_between > 0:
        return round((last_weight - first_weight) / days_between, 3)
    return 0

# ============================================================================
# TEMPLATE FILTERS
# ============================================================================

@app.template_filter('ksh')
def ksh_filter(amount):
    """Format amount as Kenyan Shillings"""
    if amount is None:
        return "Ksh 0.00"
    return f"Ksh {float(amount):,.2f}"

@app.template_filter('date_format')
def date_format_filter(date_obj, format='%d/%m/%Y'):
    """Format date"""
    if date_obj:
        return date_obj.strftime(format)
    return ""

@app.template_filter('time_format')
def time_format_filter(date_obj, format='%H:%M'):
    """Format time"""
    if date_obj:
        return date_obj.strftime(format)
    return ""

# ============================================================================
# FILE UPLOAD HANDLER
# ============================================================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if request.is_json:
        return jsonify({'error': 'Not found'}), 404
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    if request.is_json:
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    if request.is_json:
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('errors/403.html'), 403

# ============================================================================
# API ENDPOINTS FOR AJAX CALLS
# ============================================================================

@app.route('/api/tasks/today')
@login_required
def api_today_tasks():
    """Get today's tasks for current user"""
    tasks = Task.query.filter(
        Task.assigned_to == current_user.id,
        Task.due_date == date.today(),
        Task.status.in_(['Pending', 'In Progress'])
    ).all()
    
    return jsonify([{
        'id': t.id,
        'title': t.task_title,
        'priority': t.priority,
        'status': t.status,
        'due_date': t.due_date.strftime('%Y-%m-%d') if t.due_date else None
    } for t in tasks])

@app.route('/api/livestock/search')
@login_required
def api_search_livestock():
    """Search livestock by tag or name"""
    query = request.args.get('q', '')
    
    animals = Livestock.query.filter(
        (Livestock.tag_number.ilike(f'%{query}%')) |
        (Livestock.name.ilike(f'%{query}%'))
    ).filter_by(is_active=True).limit(10).all()
    
    return jsonify([{
        'id': a.id,
        'tag_number': a.tag_number,
        'name': a.name,
        'category': a.category.name
    } for a in animals])

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """Get dashboard statistics via API"""
    stats = {
        'livestock_count': Livestock.query.filter_by(is_active=True).count(),
        'active_crops': CropPlanting.query.filter_by(status='Active').count(),
        'pending_tasks': Task.query.filter_by(status='Pending').count(),
        'employees_present': Attendance.query.filter_by(
            attendance_date=date.today(),
            status='Present'
        ).count(),
        'monthly_revenue': float(db.session.query(func.sum(FarmIncome.total_amount)).filter(
            extract('month', FarmIncome.income_date) == datetime.now().month,
            extract('year', FarmIncome.income_date) == datetime.now().year
        ).scalar() or 0),
        'sick_animals': Livestock.query.filter_by(
            health_status='Sick',
            is_active=True
        ).count()
    }
    
    return jsonify(stats)

@app.route('/api/notifications')
@login_required
def api_notifications():
    """Get user notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'link': n.link,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@app.route('/settings')
@login_required
@admin_required
def system_settings():
    """System settings page"""
    settings = SystemSetting.query.all()
    return render_template('settings/index.html', settings=settings)

@app.route('/settings/save', methods=['POST'])
@login_required
@admin_required
def save_settings():
    """Save system settings"""
    for key, value in request.form.items():
        if key != 'csrf_token':
            setting = SystemSetting.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = value
                setting.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Settings saved successfully!', 'success')
    return redirect(url_for('system_settings'))

# ============================================================================
# SUPPLIER MANAGEMENT ROUTES
# ============================================================================

@app.route('/suppliers')
@login_required
def supplier_list():
    """List suppliers"""
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_supplier():
    """Add supplier"""
    if request.method == 'POST':
        supplier = Supplier(
            supplier_name=request.form.get('supplier_name'),
            supplier_code=request.form.get('supplier_code') or generate_reference_number('SUP'),
            contact_person=request.form.get('contact_person'),
            phone_number=request.form.get('phone_number'),
            email=request.form.get('email'),
            physical_address=request.form.get('physical_address'),
            county=request.form.get('county'),
            town=request.form.get('town'),
            category=request.form.get('category'),
            payment_terms=request.form.get('payment_terms'),
            bank_name=request.form.get('bank_name'),
            bank_account=request.form.get('bank_account'),
            kra_pin=request.form.get('kra_pin'),
            notes=request.form.get('notes')
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        flash('Supplier added!', 'success')
        return redirect(url_for('supplier_list'))
    
    return render_template('suppliers/add.html')

# ============================================================================
# NOTIFICATION ROUTES
# ============================================================================

@app.route('/notifications')
@login_required
def notification_list():
    """View all notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    return render_template('notifications/list.html', notifications=notifications)

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    flash('All notifications marked as read!', 'success')
    return redirect(url_for('notification_list'))

# ============================================================================
# MAIN APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Create default admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                employee_id='EMP20240001',
                username='admin',
                email='admin@farmmanager.com',
                first_name='Farm',
                last_name='Administrator',
                role='admin',
                department='Management',
                employment_type='Permanent',
                employment_date=date.today(),
                is_active=True,
                email_verified=True,
                basic_salary=50000
            )
            admin.set_password('admin123')  # CHANGE THIS IN PRODUCTION!
            db.session.add(admin)
            
            # Create default livestock categories
            default_categories = [
                ('Cattle (Ng\'ombe)', 'Dairy and beef cattle including Friesian, Jersey, Ayrshire, Guernsey, Boran, Zebu'),
                ('Goats (Mbuzi)', 'Dairy and meat goats including Toggenburg, Saanen, Galla, East African'),
                ('Sheep (Kondoo)', 'Wool and meat sheep including Merino, Corriedale, Dorper, Red Maasai'),
                ('Poultry (Kuku)', 'Chicken, ducks, turkeys, geese including layers, broilers, indigenous'),
                ('Pigs (Nguruwe)', 'Pork and bacon pigs including Large White, Landrace, Hampshire, Duroc'),
                ('Bees (Nyuki)', 'Honey bees for honey and wax production'),
                ('Rabbits (Sungura)', 'Meat and fur rabbits including New Zealand White, California, Chinchilla'),
                ('Fish (Samaki)', 'Tilapia, Catfish, Trout for aquaculture'),
                ('Donkeys (Punda)', 'Working donkeys for transport and farm operations')
            ]
            
            for cat_name, cat_desc in default_categories:
                if not LivestockCategory.query.filter_by(name=cat_name).first():
                    category = LivestockCategory(name=cat_name, description=cat_desc)
                    db.session.add(category)
            
            # Create default crop categories
            crop_categories = [
                ('Cereals', 'Maize, Wheat, Rice, Sorghum, Millet, Barley'),
                ('Legumes', 'Beans, Peas, Groundnuts, Soybeans, Cowpeas, Green grams'),
                ('Vegetables', 'Tomatoes, Onions, Cabbages, Kales, Spinach, Carrots'),
                ('Fruits', 'Mangoes, Bananas, Avocados, Citrus, Pawpaw, Pineapples'),
                ('Root Crops', 'Potatoes, Cassava, Sweet Potatoes, Yams, Arrowroots'),
                ('Oil Crops', 'Sunflower, Sesame, Coconut, Oil Palm, Castor'),
                ('Fiber Crops', 'Cotton, Sisal, Flax'),
                ('Beverage Crops', 'Coffee, Tea, Cocoa')
            ]
            
            for cat_name, cat_desc in crop_categories:
                if not CropCategory.query.filter_by(name=cat_name).first():
                    category = CropCategory(name=cat_name, description=cat_desc)
                    db.session.add(category)
            
            # Create default financial accounts
            default_accounts = [
                ('1000', 'ASSETS', 'Asset', None, 'All farm assets'),
                ('1100', 'Current Assets', 'Asset', '1000', 'Short-term assets'),
                ('1110', 'Cash in Hand', 'Asset', '1100', 'Physical cash'),
                ('1120', 'Bank Account', 'Asset', '1100', 'Bank balances'),
                ('1130', 'Accounts Receivable', 'Asset', '1100', 'Money owed to farm'),
                ('1140', 'Inventory', 'Asset', '1100', 'Stock on hand'),
                ('1200', 'Fixed Assets', 'Asset', '1000', 'Long-term assets'),
                ('1210', 'Land', 'Asset', '1200', 'Farm land'),
                ('1220', 'Buildings', 'Asset', '1200', 'Farm structures'),
                ('1230', 'Equipment', 'Asset', '1200', 'Farm machinery'),
                ('1240', 'Livestock', 'Asset', '1200', 'Livestock value'),
                ('2000', 'LIABILITIES', 'Liability', None, 'Farm debts'),
                ('2100', 'Current Liabilities', 'Liability', '2000', 'Short-term debts'),
                ('2110', 'Accounts Payable', 'Liability', '2100', 'Money owed by farm'),
                ('2200', 'Long-term Liabilities', 'Liability', '2000', 'Long-term loans'),
                ('3000', 'EQUITY', 'Equity', None, 'Owner\'s equity'),
                ('3100', 'Owner\'s Capital', 'Equity', '3000', 'Initial investment'),
                ('3200', 'Retained Earnings', 'Equity', '3000', 'Accumulated profits'),
                ('4000', 'REVENUE', 'Revenue', None, 'Farm income'),
                ('4100', 'Crop Sales', 'Revenue', '4000', 'Income from crop sales'),
                ('4200', 'Livestock Sales', 'Revenue', '4000', 'Income from livestock sales'),
                ('4300', 'Product Sales', 'Revenue', '4000', 'Milk, eggs, honey etc.'),
                ('4400', 'Other Income', 'Revenue', '4000', 'Miscellaneous income'),
                ('5000', 'EXPENSES', 'Expense', None, 'Farm costs'),
                ('5100', 'Feed Expenses', 'Expense', '5000', 'Animal feed costs'),
                ('5200', 'Fertilizer Expenses', 'Expense', '5000', 'Fertilizer costs'),
                ('5300', 'Labour Expenses', 'Expense', '5000', 'Wages and salaries'),
                ('5400', 'Veterinary Expenses', 'Expense', '5000', 'Animal health costs'),
                ('5500', 'Chemical Expenses', 'Expense', '5000', 'Pesticides, herbicides'),
                ('5600', 'Fuel Expenses', 'Expense', '5000', 'Fuel and lubricants'),
                ('5700', 'Maintenance Expenses', 'Expense', '5000', 'Repairs and maintenance'),
                ('5800', 'Utilities', 'Expense', '5000', 'Water, electricity'),
                ('5900', 'Miscellaneous Expenses', 'Expense', '5000', 'Other expenses')
            ]
            
            for code, name, acc_type, parent_code, desc in default_accounts:
                if not FinancialAccount.query.filter_by(account_code=code).first():
                    parent = FinancialAccount.query.filter_by(account_code=parent_code).first() if parent_code else None
                    account = FinancialAccount(
                        account_code=code,
                        account_name=name,
                        account_type=acc_type,
                        description=desc,
                        parent_account_id=parent.id if parent else None
                    )
                    db.session.add(account)
            
            # Create default system settings
            settings = [
                ('farm_name', 'My Farm', 'string', 'Name of the farm'),
                ('farm_location', 'Kenya', 'string', 'Farm location'),
                ('currency', 'Ksh', 'string', 'Currency used'),
                ('working_hours_per_day', '8', 'integer', 'Standard working hours'),
                ('overtime_multiplier', '1.5', 'float', 'Overtime rate multiplier'),
                ('annual_leave_days', '21', 'integer', 'Annual leave entitlement'),
                ('sick_leave_days', '7', 'integer', 'Annual sick leave'),
                ('maternity_leave_days', '90', 'integer', 'Maternity leave days'),
                ('paternity_leave_days', '14', 'integer', 'Paternity leave days'),
                ('nssf_tier', 'I', 'string', 'NSSF contribution tier'),
                ('company_name', 'Farm Management Ltd', 'string', 'Registered company name'),
                ('company_kra_pin', '', 'string', 'Company KRA PIN'),
                ('company_nssf_number', '', 'string', 'Company NSSF number'),
                ('company_nhif_number', '', 'string', 'Company NHIF number'),
            ]
            
            for key, value, stype, desc in settings:
                if not SystemSetting.query.filter_by(setting_key=key).first():
                    setting = SystemSetting(
                        setting_key=key,
                        setting_value=value,
                        setting_type=stype,
                        description=desc
                    )
                    db.session.add(setting)
            
            db.session.commit()
            
            print("=" * 60)
            print("FARM MANAGEMENT SYSTEM INITIALIZED")
            print("=" * 60)
            print("Default admin login:")
            print("  Username: admin")
            print("  Password: admin123")
            print("=" * 60)
            print("IMPORTANT: Change the default password immediately!")
            print("=" * 60)
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
