// ==UserScript==
// @name         BBB Stream Controls
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the stream!
// @author       Lukas Schauer
// @match        https://*/html5client/*
// @grant        none
// ==/UserScript==

window.streamcontrol = new Object();

(function() {
    'use strict';

    var ICONS = {
        'PIP': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPAAAACHCAYAAAAoctTrAAAABmJLR0QA/wD/AP+gvaeTAAAYvUlEQVR4nO3deWBU1b0H8O+dfclksu/7vkBYI6vsCO4CQqu1tKIVamutr61WH8W2Wuv6tE/swwVaW1eUtgiiVouisphA2AJZIXsySSaZLbPP3Pv+GBkIWWYyJJmZzO/zFzP3zL0nwDd3mXN+h8lIT2ldvLDUDkJIUPn8QLlQsHhhqX3Htscz/N0ZQsjIbNi0uZHn704QQnxHASYkiFGACQliFGBCghgFmJAgRgEmJIhRgAkJYhRgQoIYBZiQIEYBJiSIUYDHCcdx0Ov7/N0NMsFQgMfJU89tx/2/+iPa2jv93RUygQh8/SDLsvim/BQcDieunjfD5w70anQoO3oaK5fP7/d+V3cv2to7odHooVSGAQAYhkGEMhzxcdGQy6U+H3O8vf7GbkyelIvbv3M9Kk5UITkp3t9dIhOETwH+z+dHsPejA1i0oBR6fR9OVdZizqwpOHe+BQCgDFeAx2PQoepGVmYqvj5UAbPFAh5z8YTvcDogFAjB5/OQlZmCfZ98ieVL5uJPL/0dWp0BiQmxSE1JgEwqgUajBwAYTWZUVZ9HS6sKekMfwuQyLJg/E/PnTnfv12y24IuvytHSqnK/ZzAY4XA43a+FQgGSEmORl5uBaVMKwTCML38Ng9Jo9fjiyzJU1zTghusW4tCRE5DLpLh+5UIAQFpq4qgdixDmzvWrGkYynXDnro8hFotw8w1L3O+dPF2DllYVsjNTAQA6vQFmsxVpqYlQdaqRlBiLzIyUYff76ONbodcbcd+Pv4eszOHbXsCyLD748HMc/uYkpFIxHA4npBIxFi24CkWF2QPay2VS2O0O2Ox2qFRq1NQ14JvyUxAKBVCGK7Bk0SxMm1IIAPjks4P4puwUWI5Ffm4mVl4zH1KJGBKJeMB+X96+Ez09WvRqdIiLjcLSxbNRXJiDV3a8h3lzpmHGtGKvfh5CRmLDps2NIw7wRNXXZ8KefV/g+MkqcByHZUvmYNni2eDz+di9dz/q6pvgdLLoM5og4PPhZJ0QCYUwmsxYsWw+Fi0o9fePQELMhk2bG32+B55owsJkuG3ddbht3XUDtl16tXEph8MJlmUhEgnHunuEDIoCfAUEAj4Avr+7QUIYfY1ESBCjABMSxOgSmoQcrc4AjuPcr3U6A1j24mujyQS5TOZ+zeMxUCoV7teu8QgXX/sTBZgEpQ8+/BzlxyoBuIapikUiOJwOMAwDPo8Pq80GmVQCPp8Ps8UClmXB4/HAY3gQi0UAAKUyDDzexYvQcIUcfP7FZxosy0J3yfBXjuOg1Rrcr3V6A2RSCeyOi8e90I7lWLAsC0WYvF/4tVo9hEKheyCSWCRCfl4GSiblQyaTjPjvgQJMgk6vRocVy+bhpusX+7srHvX1mWB3OIbcrtMZUFVzHi9s/RusNhsA4N57bkN8XLRX+6cAk6Dz5jt7cdu669xn0kAWFiYbdntkRDgy0pNx7TVXA3CNJNzy2FY888Qvvdo/PcQiQaenV4uY6Eh/d2NMSKUSZGelormlw6v2FGBCAszNNyzB7r37vWpLASYkwCQmxELVqfaqLQWYkAAkFAr6zaAbCgWYkACUnZmKxqY2j+0owIQEIIVCjj6jyWM7CjAhAUgqlcBisXpsRwEmJABJJWKYTBaP7SjAhAQgkUgIm93usR0FmJAAJBIJYbNRgMkEdOlMoolKKpHAbB7jS2ibzY7aukYcKTvprkg5HI7j8OHHB3DiVPWVHJaEuFAIcEpyPFrbPNcQ9znAJ05V45nnd6Ds6GlodYZvy8sM74mnX0GYXIaDh4/j5e07B/xDdKt7sfejA17dvJPQJRGLvXpCG8wUCjn6+jx/jeTzbKSpJQWYWlIwos/890MbAQALry5F+bFK/OqRZ5GWmgink4Ve3wc+n4cVy+fjgQefxE9/fDsmF+cN2IdWZwDLsghXhHn1S+NyZrMFUunI512SwFFYkIWqmvPuEsChzG/TCUtnTELpjEno1egg4PMRHh7m3ja5OBd/e+sDvPH2XmRnpaK4MAdxsVH4+lAFVJ1qREdHoKurBw6nqyokAERFKhEdFYGYmEhER0UgLjYKSYlx7oqRnV09eOLpV5CakoC29i7MnT0VV82cjMiIcBw7fhaf7j8EsUgEJ+vEzOmTcPW8GYiMCMejj28Fn8cHy7HuwvR3rl+F1JSEIX82VacaL738NhZdXYpZpSWoOHEWn+4/DI7jwDAMeDzX5G8ez1VQ/qYbliA3Ow1lR0+jtr4Jd3z3BvolM4yigmwcrTgz4QPMwfOtgt/nA0dFKge8J5GIcc+GtQCAtvZOnK06hyNlJxEWJsPD63806H50egO6unrR06tFt7oX1TWuFRwsVhsYxnW/vvnXGxEbEwXAdQvw2f7DUPdoMaUkH3/47f1gGAZOpxMVJ6rw97c+QF+fCaUzJuOGa12rKtjtDlf4+MOf+RPiY7Dl4R/j4OHj2PbauyguysFv//veQT9ns9nxrz3/wUeffIWZ04tx/coFeOKZVxEml8Fms8PhdE0Gv7QfoS47Kw07d33i726MKZvNDrHI83xnvwfYk+SkeK/WElKGK6AMVyAX6V7td6hbAD6f7746uJxQ6P1fl1AowKIFpR4LvotEQqxbs7Lfe49tuc/r44QigcBVWH8iU3WqERcb5bEdfY1ESABq7+hCUlKcx3YUYEICkKpTjYT4GI/tKMCEBKAOVTeSEukMTEhQ6u7WICY6wmM7CjAJOg6HEwIP3wQEO5ZjPX7bAVCASRAaxfXYg15AB1inN6ClVeXvbpAAw+fz4XSy/u5GQAjI74FbWlXY9tq7UITJYbc78JuHN7m3sSyLf+3Zj6MVleDz+a7FuBfPoQW2Q4w3o5RCQcAF+NW/vA+1WoPND22EVCrB0/+zHUajGXK5FF98WY7de/dj7eoVeOJ3P3d/ZstjL1KAyYTi7YyrKwqwzWZ3LSzlwxIXWp0Bu/75bzicTmy8ax16NTo8/uQ2rFuzErOvmuJuV5CfhZq6BpQdPQ2ZVILnn35owL4K87PxzPM7wHEc4uNikJAQg3mzp7mXtbBabag714RJRbm+/7CEjKMwucx94hrOFQW4uaUDO3d9DIvV6hqkz/Dwm4c39Vvx7YLWNteY5lOVNdBo9YhQKrDqpmXo7OrBU89tR69Ghy2P3Dtg2caM9GS8tO0trLxmPlbdtGzQfty27joArqB2dvWguaUDz/7pL0hOikdqSgIOfFWO9LQk7Pv4Sxj6TFi3ZsWgM51IaGNZFl8dPIam5nbMmF6M4sIcv/VFIhHDarONbYBzstPwyIP3eGz3xNOvICYmEsWFObj7zlv7hTQnOw35eRlDrnWTnpaIb8pP4eWtv/V4HLFYhLTURKSlJmL+3On4pvwUWts68cffP+Buw3Ecvrv+l8jNSQefzwPLciidMQkrls0LisWyyOgxmy34pvw0WttUaG3rhEarx5JFszBvznQcOnIcb76zFyKREHk5GVi7esWIxsJfKT6fB6fT83jvcemRp5APt1CVMlyBPbv+7NNxZ5WWYNZlt8YMw+DuH67B8qVzAbgCXXb0NJ56bjusNhtmXzUF1yydS2EOcAx8/y7J6XTilR3vob2jG0sWzkLpjElYc8vyflM4s7NS3X8+eboGTz77GkQiIb5/+41ejZC6Unw+36uVGQLuIdZghpt764sL4QVcgXYFvQQcx+FI2Uk8+exr4PF42PCDVUhOiofNZodIJMTZqnMoKswe1b6QkXM4nD4Vc2BZFge+Oop/fvAZfrThVq9vo6ZMzseUyfkAgMamNjzy6At44L717qmpY4HjuEFvRS8XFAEeLwzDYM6sqZgzaypMJgveeW8fdPo+nDhVjdzsNNx84xJ/d5EA0Bv6oFDIvW7foerG9r/ugtlixcL5pXj+6Ye8GuU0mIz0ZPzy53di+193QW8wYu3qFSiZNPrPU5xO1l3wYTgU4CHIZBJs+MFqsCyLru5er2aGkPHR1NyO9LQkr9pWnq3DG2/vweaHNnlcbNtbUZFK/OqBDbBabXh75z68949PcP9P7hjVNYudTicEAs/xpAB7wOPxKLwB5szZeswqLfHYzmAw4tUd7+P5px/y6nJ0pMRiEX74/VvQq9Hhtb+8D41Wj8ULZmHp4lk+n+GNRjNe2fEeutUa8OkSmkxEteeasHjhVcO2cTqd2PLYVmz+9cYxCe+loiKVePC/7nLfY//m9y8iOioCy5fORUZaUr96b8NxOJzY9tq7WLp4Nj4/UObVZyjAJOjYbXbs+ten0Gj0MFssCFeEwdBnhFgsgkjoKmJo6DPip5tuH9MHTZfj8XhYvPAqLF54Fbq6e/H1oQr8+7ODUPdoMLWkANevXDjg3r2hsRVHyk6htq4RWp0B69aswNSSApQfq4SqU+0x/BRgEnSEQgF+du8d/u7GsOJio7D65osDj05V1uLPr7wDo8kEPo8PhmHgcDqQmZ6CWaUl+M6tK/tdKWSkJaFbrUFebsawx6EAk6Ci0xsQGTGwkmmgK5mUN6Kn1dHREWhr7/LYLqCnExJyuda2TqQke65SGuzkMqlXKzNQgElQsViskEjE/u5GwKAAk6Di7bKboYICTIKKa5qd50vLUOHzQ6z2ji68/sZuSKVi/Pyn60ezT4QMSSqVwOTFurmhwucAR0aE4xf3/xB2u8Nj29NnalFX3wyDwQirzTZgu1wmhUgkhEwmgVgkgkwmhVgshFQiQWRkOCQSMaQSMd37EDBU0a4fnwN8YerVhdX/hnLw8HE0Nbdj2pTCYafoGU0m2Gx2mEwWmExmqHs0MBrNaG7pAOAaWWM0mTG1pABrV6/wtdskyOl0BijCvJ/IMNGN+ffA8+ZMw7w500Ztfy9v34ktj72IlOQE5GanIyc7DSnJ8T79ZnY6nTh4+DiOVpyBVqfHsYqz2LPrpTEfejfaTp6uQVFB9rhOOPeXs9XnUJCf6e9uBIyg+xffeNc6AK5lR+vqm/Hxp1+jta1/6dnUlATkZKWjsCAL8XHRA/bR3NKBt979EIY+IxbOL8WGH6xGhFKBihNnseWxrRAI+LjjuzciJzttXH4mm82OoxVnMGfWFFRVn4fD6URRQbZXc17PVp3DtlffxZpblmPZkjnj0Fv/qjxTh2uvudrf3QgYQRfgCy4sO3p5NUqO49DSqkL9uWb8Y/en6FB1g+MAqUSMBfNnYt8nXyI5KR4b716HyIjwfp+dPrUI06cWwWy24PU3d+O1v74Ph8Ppvje/5aalKMzPQkurClqdAVqtHqfP1KG1TYVZpSVYddMyWCxWHDx8HOcaWjBzejGmTy0a0Pea2gbs2fcFNFo9hEIBOI7D5OI8/OGpl5GXmwE+n49/7P4UHMeB4zjIZTKkpyVixrRi5GSnua82Pv70axw9VomXXtgcdFcNvrLZ7VQt5RJBG+ChMAzjrou1ZNEs9/tGoxn//s9BPPSLu6AMVwyzB9f9/aa7v9PvPYPBiBf/703s3PUx0lISERERjuioCNy66hokxMdg8+/+FxUnqiASCrFg/gzccO1CfH2oAns+/AIcOPAYHjiOg81uR15OBu5cvwrRUUOvfbPmluXuP5vNFjQ2teNI2Um8+e5eAK4J31NLCrD515uG2sWERA+x+ptwAR6KXC4dsqqlNxQK+bC1vR5/9GcD3rt84W5fSaUSFBZkobAga1T2F6za2jvHpR5VMAmN6y4yIVScqBr0liSUUYBJ0DhdWYtJRf6r1RyIKMAkaFhttn6lXwkFmJCgRgEmQcHpdELAD5lnruA4UFlZMnEwDAOtTo9HH98KhmEgFomQmpKAjPRkpKUmIikxzqdi74FKpzd4VQyPAkyCAo/Hw3NPPuh+bbFY0dTcjpZWFT7bfxjNrR2wWKwAXMuS8Pk894J7GenJiI2NRGxMFOLjohEbEzmm99LNLR3Ys+8LdHX3uPsAAEplGIoKssEwDHT6PrAsC4vFCvO3/Rbw+UhIiME1S+ehq7sXWZkpHo9FASZBSSIRIz8vE/l5w4+LdjicaG1TQdWpRmdXDyrP1KGruxdGkwk8Hg88hgeL1QqWZb065oU1mZTKMMhkF1cONJnM0On64HA6ERcbhbWrVwyoJ97Tq0VjUxsAIDIyHGFyGYTfVtFkGNfEoKbmDjzy6AvQaPTY9uIWj32iAJMJTSDgIyM9GRnpyaO6X53eAJblYLc7YLFYoVDIoQwPG3ZIa3RUxLCj7wDXEOG5s6d63Q8KMCE+8DQcd7zQU2hCgpjPATYazehW96L8WCWamtu9/pyqU+3rIQkhl/H5Elqj1WP33v1ITIjFjGnej0/94MPPodUa0KvRIkIZDoZhIJWI0a7qAsMwiFCGY8a0opCY20rIlfI5wCnJ8fjJxttG/Ll7Nqz19ZCEkMvQPTAhQYwCTEgQowATEsQowIQEMQowIUGMRmKRoKDTG2A2W/3djYBitzl4fglw+bFK6PV9WLp4tj8OT4LQmbZ2RGUl+bsbAWXKgmlR4x7gl7fvRHRUBNraO5GZkeLVlClCRGIRwiMCY/xxoBCKhNy4B/jCygplR0+juvY8BZgEJZvVhpbGNghFQqT58f+w3x5ilR+rxNVzZ/jr8IR4xWK2oKGuCWbTxSVNO1o70drUjuz8TMQnxqK+ugHnahrAcdy49++KzsANja3Y8bd/Qhke5nGlgcv5MgyTkPGk7upFn74Pmbnp6GjtxPm6Jug1OojFYiijwtF0rgU2mx2JKfGQyaVorG92h/jCvOD4pDhIZWNX/eOKApyZkYLHttw34s+VH6tEVfU5rP/ezVdyeELGREujq2qGWCxCRo5rgbvElHgkpsQP2r76dB0UyjBk5qYP2Nbc0AqhUDjkZ6+UX55CP//i67huxQJ/HJqQYRl0BjgdTndwvVEwORcmownVp2sBhoFYLALDMGBZFhzHwWK2wlRjQvYYLIvqlwCvXb1i3JbuJMRbDrsDXSo1svMzUXmiCskpiYiM8e62UCaXoWBy3qDbLGYLmhvacfTQCdisNsxeOHPUVpP0y0OsVTctw+TiwX9YQvzlsw8PICk1EWUHK5CYHO91eD2RSCXIK8pC0ZR8GPtMKPv6+KjsF6ChlIQAAGrO1EMgEODMiSokpSQgOjZq9I9RWYecgkxExUZA3dU7KvukABMCoFulBl/AR0RUBFLS+4/4MpssaG3yvmzUUOISYxGXEAuBQDBqT6YpwCTkfbJ7P04dO4OiyfmIiFL229ar1kDV1om4hBiPIT5f24jO9i5YLYOP2U5OS4SqvRNpmSmQh8lGpe8UYBLyeDwe7rhnHbRaHWLi+l8693RrkJmbDp3WgDCFfMh9NDe0AgDkCjmaG9qGbMfn80d1CRgKMAl5y29chJ7uXmQN8j2u1WJFY30zDDrDgLPzpWxWO1IzktGtUkMRPnTQRxtNJyQhz+FwAgCEIuGAbZOmFXq1j5yCTLQ0tiE1M2VcF1mjMzAJefXV50c0cGMoqRnJ475CIgWYhDSO4yAUCsAwntfiDUQUYBLSGuubkT7CUYENdU3Qaw1j1KORoQCTkMay7Igvezs7umEymsaoRyNDD7FISPNlTPLsBTN9OlavWoOomEifPjsUOgMTMk60vbpRLwtEASYhbbSqaAw1+mosjnUpCjAJaQzDDBs+juOg0+iH3UdrUztYdvhwqto6kZA8+pP6KcAkpGXmpqOlsR093YPPDmIYBqr2LljMlkG396o14DjO4+QEY59p1MY/X4oCTEJeTkEmHHYHms63Dro9vzgHXSo16qsb0NbcAQDo6e7FuZoG2G2uIZTD6eroRmx8zKj3G6Cn0IQAcBWf6zMYUV1Zh4JJuQO2Xygda7VYcb62EZHREV6VyGFZFjqtAXGJsaPeZ4DOwIS4hSnkyCnIwpkT1e7x0ZcTS8TIystAZLR31Tpqz9Qjp2D0a2FdQGdgQi4hEPBRPLUA52oaIBAKkZaZPOQwy872LtjtjgEFABx2B1oa22C1WJGRkzamwzQpwIQMIjs/E23NHbDb7BCJRYO2MRnNSElPwvnaRvD5fDidF2c1jXVwL6AAEzIEq8U6ZHiBbydCiITIyssYv05dhu6BCfFRIMxgogATMgiDbvgSOgAQFh4GTY92nHo0OAowIYNQtXd7/OonNj4aBn2feykWf6AAE3KZXrUGSi8nHaRlpiA6Ngo1Z+rdgzzGEz3EIuQSHMehS6UedDDHUGRyKfKLc2AxW1Bf3QCGcdWAVoSHjWFPXSjAhFyiruo88oqyffqsRCpxD9ro6uiGqq0LygjFmI3CAugSmhC3uqrzSEyJH5WFx+ISY5FbmAWRWITas+dGoXeD4Dg6A5PQxrIsztc2gcdjkJmbPupVJSOilBCKhK6Ssx4mPYyUyWIRMrk56W3Xr1w4+MBPQgJEVFqcsnhG8agsKORwONCr1jJSuZiRKxRM/qQcZrjvdFknC5ZlPe6X5ViOdQ7err25nXPYhtjoo93vfoT/BzVrc01lVROgAAAAAElFTkSuQmCC',
        'SBS': 'data:image/png;base64,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',
        'CAM': 'data:image/png;base64,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',
        'PRES': 'data:image/png;base64,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',
    };

    console.log("Activating stream control user script");

    function uiaddon() {
        if(document.getElementById('stream-control-buttons') != undefined) return;
        var userlist = document.querySelector('div[aria-label="User list"]');
        if (userlist == undefined) {
            return;
        }
        var sidebar = document.querySelector('div[aria-label="User list"]').children[0].children[0];
        var buttons = document.createElement('div');
        buttons.id = 'stream-control-buttons';
        buttons.innerHTML = '<h2 style="font-size:0.85rem;font-weight:600;text-transform:uppercase;padding: 0 var(--sm-padding-x);">Stream Control</h2>';
        buttons.innerHTML += '<center>';
        buttons.innerHTML += '<button style="margin:0px;max-width:48%;float:left;background:none;border:none;padding:0;" onclick="streamcontrol.send_command(\'!view sbs\')"><img style="max-width:100%;" src="' + ICONS.SBS + '" /><br/>SBS</button>';
        buttons.innerHTML += '<button style="margin:0px;max-width:48%;float:right;background:none;border:none;padding:0;" onclick="streamcontrol.send_command(\'!view pip\')"><img style="max-width:100%;" src="' + ICONS.PIP + '" /><br/>PIP</button>';
        buttons.innerHTML += '<br style="clear:both" />';
        buttons.innerHTML += '<button style="margin:0px;max-width:48%;float:left;background:none;border:none;padding:0;" onclick="streamcontrol.send_command(\'!view cam\')"><img style="max-width:100%;" src="' + ICONS.CAM + '" /><br/>CAM</button>';
        buttons.innerHTML += '<button style="margin:0px;max-width:48%;float:right;background:none;border:none;padding:0;" onclick="streamcontrol.send_command(\'!view pres\')"><img style="max-width:100%;" src="' + ICONS.PRES + '" /><br/>PRES</button>';
        buttons.innerHTML += '</center>';
        sidebar.prepend(buttons);
    }

    function dec2hex (dec) {
        return dec.toString(16).padStart(2, "0")
    }

    // generateId :: Integer -> String
    function generateId (len) {
        var arr = new Uint8Array((len || 40) / 2)
        window.crypto.getRandomValues(arr)
        return Array.from(arr, dec2hex).join('')
    }

    function streamcontroller() {
        if (window.sessionStorage.BBB_authToken == undefined) {
            setTimeout(streamcontroller, 100);
            return;
        }
        var socket = new WebSocket(window.location.href.split("/join")[0].replace("https", "wss") + "/sockjs/494/" + generateId(8) + "/websocket")
        var users = {};
        var chats = {};
        var STREAM_USER = 'stream';

        function send(msg) {
            socket.send(JSON.stringify([JSON.stringify(msg)]))
        }

        function send_command(command) {
            for (var id in users) {
                if(users[id].name == STREAM_USER) {
                    console.log("Sending to " + users[id].userId);
                    chatmsg(chats[users[id].userId], command);
                }
            }
        }
        window.streamcontrol.send_command = send_command;

        function chatmsg(target, msg) {
            send({'msg': 'method', 'method': 'sendGroupChatMsg', 'params': [target, {'color': '0', 'correlationId': window.sessionStorage.BBB_userID + '-' + String(Date.now()), 'sender': {'id': window.sessionStorage.BBB_userID, 'name': window.sessionStorage.BBB_fullname}, 'message': msg}], 'id': String(Date.now())});
        }

        function onmessage(e) {
            if (e.data == 'o') return;
            var msg = JSON.parse(JSON.parse(e.data.substr(1))[0]);
            if (msg.msg == 'ping') {
                send({'msg': 'pong'})
            }

            //if (msg.msg == 'updated' && msg.methods[0] == "2") {
            //    chatmsg('MAIN-PUBLIC-GROUP-CHAT', 'Hello, World! :)');
            //}

            if (msg.collection == 'group-chat') {
                for (var i in msg.fields.users) {
                    if (msg.fields.users[i] == window.sessionStorage.BBB_userID) continue;
                    chats[msg.fields.users[i]] = msg.fields.chatId;
                }
            }

            if (msg.collection == 'users') {
                if(msg.msg == 'added') {
                    users[msg.id] = msg.fields;
                    users[msg.id]._id = msg.id
                } else if(msg.msg == 'changed') {
                    for (var key in msg.fields) {
                        users[msg.id][key] = msg.fields[key]
                    }
                } else {
                    return;
                }
                if(users[msg.id].name == STREAM_USER) {
                    if(chats[users[msg.id].userId] == undefined) {
                        send({'msg': 'method', 'method': 'createGroupChat', 'params': [users[msg.id]], 'id': 'chat-' + users[msg.id].userId})
                    }
                }
            }
        }

        function onopen() {
            console.debug("Websocket connection established.");
            send({'msg': 'connect', 'version': '1', 'support': ['1', 'pre1', 'pre2']});
            send({'msg': 'method', 'method': 'userChangedLocalSettings', 'params': [{'application': {'animations': true, 'chatAudioAlerts': false, 'chatPushAlerts': false, 'fallbackLocale': 'en', 'overrideLocale': null, 'userJoinAudioAlerts': false, 'userJoinPushAlerts': false, 'locale': 'en-US'}, 'audio': {'inputDeviceId': 'undefined', 'outputDeviceId': 'undefined'}, 'dataSaving': {'viewParticipantsWebcams': true, 'viewScreenshare': true}}], 'id': '1'});
            send({'msg': 'method', 'method': 'validateAuthToken', 'params': [window.sessionStorage.BBB_meetingID, window.sessionStorage.BBB_userID, window.sessionStorage.BBB_authToken, window.sessionStorage.BBB_externUserID], 'id': '2'})
            send({'msg': 'sub', 'id': 'sub-group-chat', 'name': 'group-chat', 'params': []});
            send({'msg': 'sub', 'id': 'sub-group-chat-msg', 'name': 'group-chat-msg', 'params': []});
            send({'msg': 'sub', 'id': 'sub-users', 'name': 'users', 'params': []});
        }
        socket.onopen = onopen;
        socket.onmessage = onmessage;
    }

    setTimeout(streamcontroller, 100);
    setInterval(uiaddon, 100);
})();