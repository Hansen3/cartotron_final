import stripe
from django.conf import settings

from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from shop.forms import CheckoutForm
from shop.models import Category, Product, CartItem, Invoice, Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict


stripe.api_key = settings.STRIPE_SECRET_KEY


def category_list(request):
    """
    Fetch a all of the categories from the database in ascending order by name and render a list of categories.
    """
    categories = Category.objects.all().order_by("name")
    context = {'categories': categories}

    return render(request, "shop/category_list.html", context)


def category_detail(request, category_id):
    """
    Fetch the category and a list of products with that category from the database
     and render a list of products.
    """
    category = Category.objects.get(id=category_id)
    products = Product.objects.filter(categories=category).order_by("name")

    context = {
        'category': category,
        'products': products,
    }

    return render(request, "shop/product_list.html", context)


def product_list(request):
    """
    Fetch all of the products from the database and render them in a list
    """
    products = Product.objects.all().order_by("name")
    context = {'products': products}

    return render(request, "shop/product_list.html", context)


def product_detail(request, product_id):
    """
    Fetch a product by its id from the database and render it in a detail view
    """
    product = Product.objects.get(id=product_id)
    context = {'product': product}

    return render(request, "shop/product_detail.html", context)


def cart_contents(request):
    """
    Fetch a product by its id from the database and render it in a detail view
    """
    product = Product.objects.all()
    context = {'product': product}

    return render(request, "shop/cart_contents.html", context)


def cart_add(request, product_id):

    if request.method == "POST":

        product = Product.objects.get(id=product_id)
        request.cart.add_item(product)

    return HttpResponseRedirect("/cart/")


def cart_remove(request, product_id):

    if request.method == "POST":

        product = Product.objects.get(id=product_id)
        request.cart.remove_item(product)

    return HttpResponseRedirect("/cart/")


def search(request):
    if request.method == "GET":

        search_query = request.GET['q']

        try:
            found = Product.objects.get(name=search_query)
        except ObjectDoesNotExist:
            found = ""

        if found != "":
            return HttpResponseRedirect("/products/" + str(found.id))

        try:
            found = Category.objects.get(name=search_query)
        except ObjectDoesNotExist:
            found = ""

        if found != "":
            return HttpResponseRedirect("/categories/" + str(found.id))

        return HttpResponseRedirect("/products/")


def cart_update(request):

    if request.method == "POST":

        for item, quantity in request.POST.items():

            if item.startswith("item-"):
                quantity = int(quantity)
                item_id = int(item.split("-")[1])

                if quantity <= 0:
                    request.cart.items.filter(id=item_id).delete()

                else:

                    try:
                        cart_item = request.cart.items.get(id=item_id)
                        cart_item.quantity = quantity
                        cart_item.save()
                    except CartItem.DoesNotExist:
                        pass

    return HttpResponseRedirect("/cart/")


def checkout(request):

    checkout_step = request.session.get('checkout_step', 1)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'back':
            if checkout_step == 1:

                if 'checkout_step' in request.session:
                    del request.session['checkout_step']
                return HttpResponseRedirect('/cart/')

            if checkout_step > 1:
                request.session['checkout_step'] = checkout_step - 1
                return HttpResponseRedirect('/cart/checkout/')

    if checkout_step == 1:

        if request.method == "POST":
            form = CheckoutForm(data=request.POST)

            if form.is_valid():
                # if the form was valid, proceed to checkout step two.
                # make sure to save stripe token and order information somewhere!

                token = stripe.Token.retrieve(request.POST.get('stripe_token'))

                request.session['token'] = token

                invoice = Invoice()
                invoice.name_first = form.cleaned_data['first_name']
                invoice.name_last = form.cleaned_data['last_name']
                invoice.street_1 = form.cleaned_data['address_1']
                invoice.street_2 = form.cleaned_data['address_2']
                invoice.city = form.cleaned_data['city']
                invoice.country = form.cleaned_data['country']
                invoice.province = form.cleaned_data['province']
                invoice.postal_code = form.cleaned_data['postal_code']
                invoice.phone = form.cleaned_data['phone_number']
                invoice.email = form.cleaned_data['email']
                invoice.stripe_token = request.POST.get('stripe_token')
                invoice.card_last4 = token['card']['last4']
                invoice.card_brand = token['card']['brand']

                # convert the Invoice into a dictionary for serialization into session (we'll change it back later)
                request.session['invoice'] = model_to_dict(invoice)

                request.session['checkout_step'] = 2
                return HttpResponseRedirect("/cart/checkout/")

        else:

            invoice_dict = request.session.get('invoice')

            initial = {}
            if invoice_dict:
                invoice = Invoice(**invoice_dict)
                initial['first_name'] = invoice.name_first
                initial['last_name'] = invoice.name_last
                initial['address_1'] = invoice.street_1
                initial['address_2'] = invoice.street_2
                initial['city'] = invoice.city
                initial['country'] = invoice.country
                initial['province'] = invoice.province
                initial['postal_code'] = invoice.postal_code
                initial['phone_number'] = invoice.phone
                initial['email'] = invoice.email

            form = CheckoutForm(initial=initial)

        context = {'form': form}

        return render(request, 'shop/checkout_step_1.html', context)

    # process checkout step 2
    elif checkout_step == 2:

        invoice_dict = request.session['invoice']
        invoice = Invoice(**invoice_dict)

        # handle confirm page submitted
        if request.method == 'POST':

            # set the calculated fields and save
            invoice.shipping = Decimal("10.00")
            invoice.tax = request.cart.tax()
            invoice.subtotal = request.cart.subtotal()
            invoice.total = request.cart.total() + invoice.shipping
            invoice.save()

            invoice.create_items(cart=request.cart)

            request.cart.adjust_stock()

            total_cents = int(invoice.total*100)
            stripe.Charge.create(
                amount=total_cents,
                currency='cad',
                source=invoice.stripe_token,
                description='Test Charge from checkout'
            )

            del request.session['checkout_step']
            del request.session['invoice']
            del request.session['token']
            request.cart.delete()

            # create invoice,
            # charge stripe token for cart total amount in cents
            # remove stock from inventory
            # clear checkout step from session
            # clear invoice from session

            return HttpResponseRedirect('/invoices/%s/' % invoice.id)

        else:


            # use some dictionary unpacking magic to turn our invoice_dict back into an Invoice



            context = {
                'invoice': invoice,
                'token': request.session['token']
            }
            return render(request, 'shop/checkout_step_2.html', context)

def invoice(request, invoice_id):

    invoice = get_object_or_404(Invoice, id=invoice_id)
    context = {
        'invoice': invoice,
    }

    return render(request, 'shop/invoice.html', context)