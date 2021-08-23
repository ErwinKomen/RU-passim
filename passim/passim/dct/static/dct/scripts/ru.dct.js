var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      ru.basic.init_events();
      // ru.basic.init_typeahead();

      // Initialize Bootstrap popover
      // Note: this is used when hovering over the question mark button
      $('[data-toggle="popover"]').popover();
    });
  });
})(django.jQuery);


// based on the type, action will be loaded

// var $ = django.jQuery.noConflict();

var ru = (function ($, ru) {
  "use strict";

  ru.dct = (function ($, config) {
    // Define variables for ru.basic here
    var loc_divErr = "basic_err",
        loc_urlStore = "",      // Keep track of URL to be shown
        loc_progr = [],         // Progress tracking
        loc_relatedRow = null,  // Row being dragged
        loc_params = "",
        loc_colwrap = [],       // Column wrapping
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        loc_bManuSaved = false,
        loc_keyword = [],           // Keywords that can belong to a sermongold or a sermondescr
        loc_language = [],
        KEYS = {
          BACKSPACE: 8, TAB: 9, ENTER: 13, SHIFT: 16, CTRL: 17, ALT: 18, ESC: 27, SPACE: 32, PAGE_UP: 33, PAGE_DOWN: 34,
          END: 35, HOME: 36, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, DELETE: 46
        },
        dummy = 1;

    // Private methods specification
    var private_methods = {
      /**
       * aaaaaaNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      aaaaaaNotVisibleFromOutside: function () {
        return "something";
      },

      copyToClipboard: function(elem) {
        // create hidden text element, if it doesn't already exist
        var targetId = "_hiddenCopyText_";
        var elConfirm = "";
        var isInput = "";
        var origSelectionStart, origSelectionEnd;

        try {
          // Get to the right element
          if (elem.tagName === "A") {
            elem = $(elem).closest("div").find("textarea").first().get(0);
          }
          isInput = elem.tagName === "INPUT" || elem.tagName === "TEXTAREA";
          if (isInput) {
            // can just use the original source element for the selection and copy
            target = elem;
            origSelectionStart = elem.selectionStart;
            origSelectionEnd = elem.selectionEnd;
          } else {
            // must use a temporary form element for the selection and copy
            target = document.getElementById(targetId);
            if (!target) {
              var target = document.createElement("textarea");
              target.style.position = "absolute";
              target.style.left = "-9999px";
              target.style.top = "0";
              target.id = targetId;
              document.body.appendChild(target);
            }
            target.textContent = elem.textContent;
          }
          // select the content
          var currentFocus = document.activeElement;
          target.focus();
          target.setSelectionRange(0, target.value.length);

          // copy the selection
          var succeed;
          try {
            succeed = document.execCommand("copy");
            console.log("Copied: " + target.value);
            elConfirm = $(elem).closest("div").find(".clipboard-confirm").first();
            $(elConfirm).html("Copied!");
            setTimeout(function () {
              $(elConfirm).fadeOut().empty();
            }, 4000);
          } catch (e) {
            succeed = false;
            console.log("Could not copy");
          }
          // restore original focus
          if (currentFocus && typeof currentFocus.focus === "function") {
            currentFocus.focus();
          }

          if (isInput) {
            // restore prior selection
            elem.setSelectionRange(origSelectionStart, origSelectionEnd);
          } else {
            // clear temporary content
            target.textContent = "";
          }
          
          return succeed;
        } catch (ex) {
          private_methods.errMsg("copyToClipboard", ex);
          return "";
        }

      },

      /** 
       *  createDiv - needed for resizableGrid
       */
      createDiv: function (height, colidx) {
        var div = document.createElement('div');
        div.style.top = 0;
        div.style.right = 0;
        div.style.width = '5px';
        div.style.position = 'absolute';
        div.style.cursor = 'col-resize';
        div.style.userSelect = 'none';

        // The table height determines how large the line is going to be
        div.style.height = height + 'px';
        // Set one custom attribut: the column index
        $(div).attr("colidx", colidx.toString());
        // REturn the div that has been made
        return div;
      },

      /** 
       *  colwrap_switch - switch a column on or off
       */
      colwrap_switch: function (colnum, set) {
        var lColWrap = null,
            elW = null,
            idx = -1;

        try {
          // Get the current value
          idx = loc_colwrap.indexOf(colnum);
          if (set) {
            if (idx < 0) {
              loc_colwrap.push(colnum);
            }
          } else {
            if (idx >= 0) {
              loc_colwrap.splice(idx, 1);
            }
          }
          // Set the correct 'w' parameter
          elW = document.getElementsByName("w");
          $(elW).val(JSON.stringify(loc_colwrap));
        } catch (ex) {
          private_methods.errMsg("colwrap_switch", ex);
          return "";
        }
      },

      /** 
       *  errClear - clear the error <div>
       */
      errClear: function () {
        $("#" + loc_divErr).html("");
      },

      /** 
       *  errMsg - show error message in <div> loc_divErr
       */
      errMsg: function (sMsg, ex) {
        var sHtml = "Error in [" + sMsg + "]<br>";
        if (ex !== undefined && ex !== null) {
          sHtml = sHtml + ex.message;
        }
        $("#" + loc_divErr).html(sHtml);
      },

      /** 
       *  getStyleVal - needed for resizableGrid
       */
      getStyleVal: function (elm, css) {
        return (window.getComputedStyle(elm, null).getPropertyValue(css))
      },

      /** 
       *  paddingDiff - needed for resizableGrid
       */
      paddingDiff: function (col) {
        if (private_methods.getStyleVal(col, 'box-sizing') == 'border-box') {
          return 0;
        }

        var padLeft = private_methods.getStyleVal(col, 'padding-left');
        var padRight = private_methods.getStyleVal(col, 'padding-right');
        return (parseInt(padLeft) + parseInt(padRight));
      },

      /**
       * prepend_styles
       *    Get the html in sDiv, but prepend styles that are used in it
       * 
       * @param {el} HTML dom element
       * @returns {string}
       */
      prepend_styles: function (sDiv, sType) {
        var lData = [],
            el = null,
            i, j,
            sheets = document.styleSheets,
            used = "",
            elems = null,
            tData = [],
            rules = null,
            rule = null,
            s = null,
            sSvg = "",
            defs = null;

        try {
          // Get the correct element
          if (sType === "svg") { sSvg = " svg"; }
          el = $(sDiv + sSvg).first().get(0);
          // Get all the styles used 
          for (i = 0; i < sheets.length; i++) {
            try {
              rules = sheets[i].cssRules;
            } catch (ex) {
              // Just continue
            }
            for (j = 0; j < rules.length; j++) {
              rule = rules[j];
              if (typeof (rule.style) !== "undefined") {
                elems = el.querySelectorAll(rule.selectorText);
                if (elems.length > 0) {
                  used += rule.selectorText + " { " + rule.style.cssText + " }\n";
                }
              }
            }
          }

          // Get the styles
          s = document.createElement('style');
          s.setAttribute('type', 'text/css');
          switch (sType) {
            case "html":
              s.innerHTML = used;

              // Get the table
              tData.push("<table class=\"func-view\">");
              tData.push($(el).find("thead").first().get(0).outerHTML);
              tData.push("<tbody>");
              $(el).find("tr").each(function (idx) {
                if (idx > 0 && !$(this).hasClass("hidden")) {
                  tData.push(this.outerHTML);
                }
              });
              tData.push("</tbody></table>");

              // Turn into a good HTML
              lData.push("<html><head>");
              lData.push(s.outerHTML);
              lData.push("</head><body>");
              // lData.push(el.outerHTML);
              lData.push(tData.join("\n"));

              lData.push("</body></html>");
              break;
            case "svg":
              s.innerHTML = "<![CDATA[\n" + used + "\n]]>";

              defs = document.createElement('defs');
              defs.appendChild(s);
              el.insertBefore(defs, el.firstChild);

              el.setAttribute("version", "1.1");
              el.setAttribute("xmlns", "http://www.w3.org/2000/svg");
              el.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
              lData.push("<?xml version=\"1.0\" standalone=\"no\"?>");
              lData.push("<!DOCTYPE svg PUBLIC \"-//W3C//DTD SVG 1.1//EN\" \"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd\" >");
              lData.push(el.outerHTML);
              break;
          }

          return lData.join("\n");
        } catch (ex) {
          private_methods.showError("prepend_styles", ex);
          return "";
        }
      },

      /**
       * resizableGrid
       *    Set the table to have resizable columns
       *    
       *    Idea: https://www.brainbell.com/javascript/making-resizable-table-js.html
       *
       */
      resizableGrid: function (elTable) {
        var row = null,
            cols = null,
            div = null,
            eltarget = null,
            tableHeight = 0;

        try {
          // Get the row and the columns
          row = $(elTable).find("tr").first();
          cols = $(row).children();

          // Sanity:
          if (!cols) return;

          // Get the table height and the table width
          tableHeight = elTable.offsetHeight;
          // Add a div with a listener
          for (var i = 0; i < cols.length; i++) {
            div = private_methods.createDiv(tableHeight, i);
            cols[i].appendChild(div);
            cols[i].style.position = 'relative';
            cols[i].style.cursor = 'pointer';
            private_methods.setListeners(div);
            // Need to add an event, but where?
            if ($(cols[i]).find("span.sortable").length > 0) {
              // We need to be able to sort
              eltarget = $(cols[i]).find("span.sortable").find("span").last();
              $(eltarget)[0].addEventListener('click', private_methods.toggle_column);
            } else {
              // Add a click event listener to the <th> column
              cols[i].addEventListener('click', private_methods.toggle_column);
            }
          }

        } catch (ex) {
          private_methods.errMsg("resizableGrid", ex);
        }
      },

      /** 
       *  setListeners - needed for resizableGrid
       */
      setListeners: function (div) {
        var pageX,
            curCol,
            nxtCol,
            colidx,
            rows,
            curColWidth,
            nxtColWidth;

        // What happens when user clicks on a mouse
        div.addEventListener('mousedown', function (e) {
          curCol = e.target.parentElement;    // The column where the cursor is
          nxtCol = curCol.nextElementSibling; // The next column
          pageX = e.pageX; 
          colidx = parseInt($(e.target).attr("colidx"), 10);
 
          var padding = private_methods.paddingDiff(curCol);
 
          curColWidth = curCol.offsetWidth - padding;
          if (nxtCol)
            nxtColWidth = nxtCol.offsetWidth - padding;

          // Set what the rows are
          rows = $(e.target).closest("table").find("tbody tr");
        });

        // What happens when user hovers over
        div.addEventListener('mouseover', function (e) {
          e.target.style.borderRight = '2px solid #0000ff';
        })

        // The mouse goes out of the area of attention
        div.addEventListener('mouseout', function (e) {
          e.target.style.borderRight = '';
        })

        // User is moving the mouse
        document.addEventListener('mousemove', function (e) {

          if (curCol) {
            var diffX = e.pageX - pageX;
 
            if (nxtCol) {
              nxtCol.style.width = (nxtColWidth - (diffX)) + 'px';
              nxtCol.style.maxWidth = (nxtColWidth - (diffX)) + 'px';
            }

            curCol.style.width = (curColWidth + diffX)+'px';
            curCol.style.maxWidth = (curColWidth + diffX) + 'px';

            // Make sure the width of all table columns at this position is set
            
            $(rows).each(function (idx, el) {
              var td = $(el).find("td")[colidx];
              td.style.maxWidth = curCol.style.maxWidth;
              td.style.width = curCol.style.maxWidth;
            });
          }
        });

        // User does mouse 'up'
        document.addEventListener('mouseup', function (e) {
          curCol = undefined;
          nxtCol = undefined;
          pageX = undefined;
          nxtColWidth = undefined;
          curColWidth = undefined
        });
      },

      /** 
       *  sortshowDo - perform sorting on this <th> column
       */
      sortshowDo: function (el) {
        var elTable = $(el).closest("table"),
            elTbody = $(elTable).find("tbody").first(),
            elTh = $(el).closest("th"),
            elSortable = $(el).closest(".sortable"),
            rows = null,
            sDirection = "desc",
            sSortType = "text",   // Either text or integer
            elDiv = null,
            colidx = -1;

        try {
          // Find out which direction is needed
          if ($(el).hasClass("fa-sort-down")) sDirection = "asc";
          if ($(elSortable).hasClass("integer")) sSortType = "integer";
          // restore direction everywhere in headers
          $(el).closest("tr").find(".fa.sortshow").each(function (idx, elSort) {
            $(elSort).removeClass("fa-sort-down");
            $(elSort).removeClass("fa-sort-up");
            $(elSort).addClass("fa-sort");
          });
          switch (sDirection) {
            case "asc":
              $(el).removeClass("fa-sort");
              $(el).addClass("fa-sort-up");
              break;
            case "desc":
              $(el).removeClass("fa-sort");
              $(el).addClass("fa-sort-down");
              break;
          }
          // Get the colidx
          elDiv = $(elTh).find("div[colidx]").first();
          if ($(elDiv).length > 0) {
            // Get the column index 0-n
            colidx = parseInt($(elDiv).attr("colidx"), 10);

            private_methods.sortTable(elTable, colidx, sDirection, sSortType);

            // Show that changes can/need to be saved
            $(elTable).closest("div").find(".related-save").removeClass("hidden");

          }
        } catch (ex) {
          private_methods.errMsg("sortshowDo", ex);
        }
      },

      /** 
       *  sortTable - sort any table on any colum into any direction
       *              @sorttype is either 'text' or 'integer' (if defined)
       */
      sortTable: function (elTable, colidx, direction, sorttype) {
        var rows = $(elTable).find('tbody  tr').get();

        // Make sure to set sorttype to something
        if (sorttype === undefined) sorttype = "text";

        // The sorttype determines the sort function
        if (sorttype == "integer") {
          rows.sort(function (a, b) {
            var A = 0, B = 0, sA = "", sB = "";

            // Get the numerical values of A and B
            sA = $(a).children('td').eq(colidx).text().match(/\d+/);
            sB = $(b).children('td').eq(colidx).text().match(/\d+/);
            if (sA !== "") A = parseInt(sA.join(''), 10);
            if (sB !== "") B = parseInt(sB.join(''), 10);

            switch (direction) {
              case "desc":
                if (A < B) { return -1; } else if (A > B) { return 1; } else return 0;
              case "asc":
                if (A < B) { return 1; } else if (A > B) { return -1; } else return 0;
            }

          });
          $.each(rows, function (index, row) {
            $(elTable).children('tbody').append(row);
          });
        } else {
          rows.sort(function (a, b) {
            var A = $(a).children('td').eq(colidx).text().toUpperCase();
            var B = $(b).children('td').eq(colidx).text().toUpperCase();

            switch (direction) {
              case "desc":
                if (A < B) { return -1; } else if (A > B) { return 1; } else return 0;
              case "asc":
                if (A < B) { return 1; } else if (A > B) { return -1; } else return 0;
            }

          });
          $.each(rows, function (index, row) {
            $(elTable).children('tbody').append(row);
          });
        }

      },

      /**
       * converts an svg string to base64 png using the domUrl
       * @param {string} svgText the svgtext
       * @param {number} [margin=0] the width of the border - the image size will be height+margin by width+margin
       * @param {string} [fill] optionally backgrund canvas fill
       * @return {Promise} a promise to the bas64 png image
       */
      svgToPng: function (svgText, options /*margin,fill */) {
        var margin, fill;

        // convert an svg text to png using the browser
        return new Promise(function (resolve, reject) {
          var match = null,
              height = 200,
              width = 200;

          try {
            // can use the domUrl function from the browser
            var domUrl = window.URL || window.webkitURL || window;
            if (!domUrl) {
              throw new Error("(browser doesnt support this)")
            }
        
            // figure out the height and width from svg text
            if (options.height) {
              height = options.height;
            } else {
              match = svgText.match(/height=\"(\d+)/m);
              height = match && match[1] ? parseInt(match[1], 10) : 200;
            }
            if (options.width) {
              width = options.width;
            } else {
              match = svgText.match(/width=\"(\d+)/m);
              width = match && match[1] ? parseInt(match[1], 10) : 200;
            }
            margin = margin || 0;
        
            // it needs a namespace
            if (!svgText.match(/xmlns=\"/mi)){
              svgText = svgText.replace ('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ') ;  
            }
        
            // create a canvas element to pass through
            var canvas = document.createElement("canvas");
            canvas.width = height+margin*2;
            canvas.height = width+margin*2;
            var ctx = canvas.getContext("2d");
        
        
            // make a blob from the svg
            var svg = new Blob([svgText], {
              type: "image/svg+xml;charset=utf-8"
            });
        
            // create a dom object for that image
            var url = domUrl.createObjectURL(svg);
        
            // create a new image to hold it the converted type
            var img = new Image;
        
            // when the image is loaded we can get it as base64 url
            img.onload = function() {
              // draw it to the canvas
              ctx.drawImage(this, margin, margin);
          
              // if it needs some styling, we need a new canvas
              if (fill) {
                var styled = document.createElement("canvas");
                styled.width = canvas.width;
                styled.height = canvas.height;
                var styledCtx = styled.getContext("2d");
                styledCtx.save();
                styledCtx.fillStyle = fill;   
                styledCtx.fillRect(0,0,canvas.width,canvas.height);
                styledCtx.strokeRect(0,0,canvas.width,canvas.height);
                styledCtx.restore();
                styledCtx.drawImage (canvas, 0,0);
                canvas = styled;
              }
              // we don't need the original any more
              domUrl.revokeObjectURL(url);
              // now we can resolve the promise, passing the base64 url
              resolve(canvas.toDataURL());
            };
        
            // load the image
            img.src = url;
        
          } catch (err) {
            reject('failed to convert svg to png ' + err);
          }
        });
      },
      /** 
       *  toggle_column - show or hide column
       */
      toggle_column: function (e) {
        var th = $(e.target).closest("th"),
            table = $(th).closest("table"),
            bSkip = false,
            tableWidth = 0,
            colid = parseInt($(th).find("div").first().attr("colidx"), 10);

        // Calculate values
        tableWidth = table[0].offsetWidth;
        // Walk all rows in the table
        $(table).find("tr").each(function (idx, el) {
          var td = null,
              width = 0,
              maxWidth = 0;

          if (idx === 0) {
            td = $(el).find("th")[colid];
            if (td.style.width.indexOf("100%") >= 0) {
              bSkip = true;
            }
          } else if (!bSkip) {
            // Get this td
            td = $(el).find("td")[colid];

            // See which way the toggling goes: check if max-width equals 10px
            if (td.style.maxWidth === "10px") {
              // Expand: remove max and min width
              width = td.style.width;
              maxWidth = td.style.maxWidth;
              // Now reset the current styling
              td.style = "";
              // Check how wide we become
              if (table[0].offsetWidth > tableWidth) {
                // Revert: we are not able to expand further
                td.style.width = width;
                td.style.maxWidth = maxWidth;
              }
            } else {
              // Shrink: set max and min width
              td.style.maxWidth = "10px";
              td.style.minWidth = "10px";
            }
          }
        });
      },

      /** 
       *  waitInit - initialize waiting
       */
      waitInit: function (el) {
        var elWaith = null;

        try {
          // Right now no initialization is defined
          return elWait;
        } catch (ex) {
          private_methods.errMsg("waitInit", ex);
        }
      },

      /** 
       *  waitStart - Start waiting by removing 'hidden' from the DOM point
       */
      waitStart: function (el) {
        if (el !== null) {
          $(el).removeClass("hidden");
        }
      },

      /** 
       *  waitStop - Stop waiting by adding 'hidden' to the DOM point
       */
      waitStop: function (el) {
        if (el !== null) {
          $(el).addClass("hidden");
        }
      }
    }
    // Public methods
    return {
      /**
       * postsubmit
       *    Submit nearest form as POST
       *
       */
      postsubmit: function (el) {
        var frm = null;

        try {
          frm = $(el).closest("form");
          // Make sure we do a POST
          frm.attr("method", "POST");
          // Submit
          $(frm).submit();
        } catch (ex) {
          private_methods.errMsg("postsubmit", ex);
        }
      }



      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

