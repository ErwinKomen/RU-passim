var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

String.prototype.format = function () {
  var formatted = this;
  for (var arg in arguments) {
    formatted = formatted.replace("{" + arg + "}", arguments[arg]);
  }
  return formatted;
};

var ru = (function ($, ru) {
  "use strict";

  ru.passim.seeker = (function ($, config) {
    // Define variables for ru.passim.seeker here
    var loc_example = "",
        loc_bManuSaved = false,
        loc_progr = [],         // Progress tracking
        loc_urlStore = "",      // Keep track of URL to be shown
        loc_goldlink_td = null, // Where the goldlink selection should go
        loc_goldlink = {},      // Store one or more goldlinks
        loc_divErr = "passim_err",
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        lAddTableRow = [
          { "table": "manu_search", "prefix": "manu", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "gftxt_formset", "prefix": "gftxt", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "gedi_formset", "prefix": "gedi", "counter": false, "events": ru.passim.init_typeahead,
            "select2_options": { "templateSelection": ru.passim.litref_template }
          },
          // super
          { "table": "scol_formset", "prefix": "scol", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "ssgeq_formset", "prefix": "ssgeq", "counter": false, "events": ru.passim.init_typeahead,
            "select2_options": { "templateSelection": ru.passim.sg_template }
          },
          { "table": "ssglink_formset", "prefix": "ssglink", "counter": false, "events": ru.passim.init_typeahead,
            "select2_options": { "templateSelection": ru.passim.ssg_template }
          },

          // gold
          { "table": "gkw_formset", "prefix": "gkw", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "geq_formset", "prefix": "geq", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "glink_formset", "prefix": "glink", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "sglit_formset", "prefix": "sglit", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "eqgcol_formset", "prefix": "eqgcol", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "gsign_formset", "prefix": "gsign", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "gcol_formset", "prefix": "gcol", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "gftxt_formset", "prefix": "gftxt", "counter": false, "events": ru.passim.init_typeahead },

          // manu
          { "table": "mprov_formset", "prefix": "mprov", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "mlit_formset", "prefix": "mlit", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "mcol_formset", "prefix": "mcol", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "mext_formset", "prefix": "mext", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "mkw_formset", "prefix": "mkw", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "mdr_formset", "prefix": "mdr", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "lrel_formset", "prefix": "lrel", "counter": false, "events": ru.passim.init_typeahead },
                    
          // sermon
          { "table": "sdcol_formset", "prefix": "sdcol", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "sdsign_formset", "prefix": "sdsign", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "stog_formset", "prefix": "stog", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "sdkw_formset", "prefix": "sdkw", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "sedi_formset", "prefix": "sedi", "counter": false, "events": ru.passim.init_typeahead },
          { "table": "srmsign_formset", "prefix": "srmsign", "counter": false, "events": ru.passim.init_typeahead }
        ];


    // Private methods specification
    var private_methods = {
      /**
       * fitFeatureBox
       *    Initialize the <svg> in the @sDiv
       * 
       * @param {object} oBound
       * @param {el} elTarget
       * @returns {object}
       */
      fitFeatureBox: function (oBound, elTarget) {
        var rect = null;

        try {
          // Take into account scrolling
          oBound['x'] -= document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] -= document.documentElement.scrollTop || document.body.scrollTop;
          // Make sure it all fits
          if (oBound['x'] + $(elTarget).width() + oBound['width'] + 10 > $(window).width()) {
            oBound['x'] -= $(elTarget).width() + oBound['width'];
          } else if (oBound['x'] < 0) {
            oBound['x'] = 10;
          }
          if (oBound['y'] + $(elTarget).height() + oBound['height'] + 10 > $(window).height()) {
            oBound['y'] -= $(elTarget).height() + oBound['height'];
          } else if (oBound['y'] < 0) {
            oBound['y'] = 10;
          } else {
            oBound['y'] += oBound['height'] + 10;
          }
          // Take into account scrolling
          oBound['x'] += document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] += document.documentElement.scrollTop || document.body.scrollTop;
          return oBound;
        } catch (ex) {
          private_methods.errMsg("fitFeatureBox", ex);
          return oBound;
        }
      },

      /**
       * methodNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      methodNotVisibleFromOutside: function () {
        return "something";
      },

      /**
       *  is_in_list
       *      whether item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @returns {boolean}
       */
      is_in_list: function (lstThis, sName) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              return true;
            }
          }
          // Failure
          return false;
        } catch (ex) {
          private_methods.errMsg("is_in_list", ex);
          return false;
        }
      },

      /**
       *  get_list_value
       *      get the value of the item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @returns {string}
       */
      get_list_value: function (lstThis, sName) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              return lstThis[i]['value'];
            }
          }
          // Failure
          return "";
        } catch (ex) {
          private_methods.errMsg("get_list_value", ex);
          return "";
        }
      },

      /**
       *  set_list_value
       *      Set the value of the item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @param {string} sValue
       * @returns {boolean}
       */
      set_list_value: function (lstThis, sName, sValue) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              lstThis[i]['value'] = sValue;
              return true;
            }
          }
          // Failure
          return false;
        } catch (ex) {
          private_methods.errMsg("set_list_value", ex);
          return false;
        }
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
          if (sType === "svg") { sSvg = " svg";}
          el = $(sDiv + sSvg).first().get(0);
          // Get all the styles used 
          for (i = 0; i < sheets.length; i++) {
            rules = sheets[i].cssRules;
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
          private_methods.errMsg("prepend_styles", ex);
          return "";
        }
      },

      /**
       * sermon_treetotable
       *    Convert the <div> oriented tree structure in [elRoot] into a list
       *      of appropriate <tr> items under <elTable>
       * 
       * @param {el}  elRoot
       * @param {el}  elTable
       * @param {el}  selectedid (optional)
       * @returns {bool}
       */
      sermon_treetotable: function (elRoot, elTable, selectedid) {
        var elTbody = null,
            elSel = null,
            elAnc = null,
            sermonid = "",
            rows = [];

        try {
          // Get a list of the <div> elements
          rows = private_methods.sermon_treelist(elRoot, selectedid);

          // Replace the rows that are there now with the new ones
          $(elTable).html("");
          $(elTable).html(rows.join("\n"));

          // Possibly find the <div.tree> that is selected
          if (selectedid !== undefined && selectedid !== "") {
            elSel = $(elRoot).find("div.tree[sermonid={0}]".format(selectedid));
            // From here find the ancestor
            elAnc = $(elSel).parentsUntil("#sermon_tree");
            // Now find all the <div.tree> that are my descendants
            $(elAnc).find("div.tree").each(function (idx, el) {
              // Get this one's sermonid
              sermonid = $(el).attr("sermonid");
              // Make sure the corresponding row is visible
              $(elTable).find("tr[sermonid={0}]".format(sermonid)).first().removeClass("hidden");
            });
          }

          return true;
        } catch (ex) {
          private_methods.errMsg("sermon_treetotable", ex);
          return false;
        }
      },

      /**
       * sermon_treelist
       *    Convert the <div> oriented tree structure in [elDiv] into a list
       *      of appropriate <tr> items under <elTable>
       * 
       * @param {el}  elDiv
       * @param {el}  selectedid (optional)
       * @returns {list}
       */
      sermon_treelist: function (elDiv, selectedid) {
        var elTbody = null,
            elTd = null,
            elSermon = null,
            elParent = null,
            sermons = [],
            sermonid = "",
            targeturl = "",
            hidden = "",
            selected = "",
            nodeid = -1,
            childof = -1,
            maxdepth = -1,
            hasChildren = false,
            colspan = 0,
            td = "",
            tr = "",
            lTr = [],
            level = -1,
            idx = -1,
            lBack = [];

        try {
          // Get all the sermons
          sermons = $(elDiv).find("div.tree");

          // Find the maximum depth
          for (idx = 0; idx < sermons.length; idx++) {
            elSermon = sermons[idx];
            level = parseInt($(elSermon).attr("level"), 10);
            if (level > maxdepth) { maxdepth = level;}
          }

          // Start creating the head
          lBack.push("<thead><tr><th colspan='{0}'>Details of this manuscript's {1} items</th><th>id</th></tr></thead>".format(maxdepth+1, sermons.length));
          lBack.push("<tbody>");

          // Walk all the sermons
          for (idx = 0; idx < sermons.length; idx++) {
            elSermon = sermons[idx];
            // The nodeid starts at 2, because '1' is reserved for the root element as parent
            nodeid = idx + 2;
            $(elSermon).attr("nodeid", nodeid);
            // Get the parent
            elParent = $(elSermon).parent(".tree");
            if (elParent === null || elParent.length === 0) {
              childof = "1";
            } else {
              childof = $(elParent).attr("nodeid");
            }

            // Get the parameters from the current sermon
            sermonid = $(elSermon).attr("sermonid");
            level = parseInt($(elSermon).attr("level"), 10);
            elTd = $(elSermon).find("span.td").first();
            td = $(elTd).html();
            targeturl = $(elTd).attr("targeturl");
            hidden = (level === 1) ? "" : " hidden";
            hasChildren = ($(elSermon).children("div.tree").length > 0);
            selected = "";
            if (selectedid !== undefined && selectedid !== "" && sermonid === selectedid) {
              selected = " selected";
            }

            // Create the <tr> myself
            lTr = [];
            lTr.push("<tr class='form-row{0}{1}' nodeid='{2}' childof='{3}' sermonid='{4}'>".format(hidden, selected, nodeid, childof, sermonid));

            if (hasChildren) {
              if (level > 1) {
                // Indicate level depth
                lTr.push("  <td class='arg-pre' colspan='{0}' style='min-width: {1}px;'></td>".format(level-1, (level-1) * 20));
              }
              // This starts a new level
              lTr.push("  <td class='arg-plus' style='min-width: 20px;' onclick='crpstudio.htable.plus_click(this, \"func-inline\");'>+</td>");
            } else {
              // Indicate level depth
              lTr.push("  <td class='arg-pre' colspan='{0}' style='min-width: {1}px;'></td>".format(level, level * 20));
            }

            // The actual content
            colspan = maxdepth - level + 1;
            // if (hasChildren) { colspan += 1;}
            lTr.push("  <td id='sermon-number-{0}' colspan='{1}' class='clickable' style='width: 100%;' targeturl='{2}' number='{0}'>".format(idx + 1, colspan, targeturl));
            lTr.push("     <span class='arg-nodeid'>{0}</span>".format(idx + 1));
            lTr.push(td);
            lTr.push("  </td>");

            // The ID of the sermon: this is used for selecting and de-selecting a row
            lTr.push("  <td class='tdnowrap clickable selectable' title='Select or de-select this row'");
            lTr.push("      onclick='ru.passim.seeker.form_row_select(this);'>{0}</td>".format(sermonid));

            // Finish the <tr>
            lTr.push("</tr>");
            tr = lTr.join("\n");

            // Add to the list
            lBack.push(tr);
          }

          lBack.push("</tbody>");

          return lBack;
        } catch (ex) {
          private_methods.errMsg("sermon_treelist", ex);
          return [];
        }
      },


      /**
       * sermon_tree
       *    Convert [elTable] into a correct TREE structure
       * 
       * @param {el}     elTable
       * @param {parent} the [nodeid] of the parent - if defined
       * @returns {object}
       */
      sermon_tree: function (elTable, row) {
        var oTree = {},
            previous = null,
            parent = null,
            children = [],
            select = [],
            rowidx = -1,
            nodeid = "",
            sermonid = "",
            search = "";

        try {
          // What is the node we have?
          if (row === undefined) {
            // We need to get the first node in the table
            select = $(elTable).find("tr.form-row");
            if (select.length > 0) {
              row = select.first();
              nodeid = $(row).attr("childof");
              sermonid = "";
              row = null;
            }
          } else {
            // Get details 
            sermonid = $(row).attr("sermonid");
            nodeid = $(row).attr("nodeid");
            rowidx = $(elTable).find("tr").index(row);
          }

          // Can we continue?
          if (nodeid !== "") {

            // Fill in the details of this node
            oTree['sermonid'] = sermonid;
            oTree['rowidx'] = rowidx;
            oTree['row'] = row;
            oTree['parent'] = null;
            oTree['next'] = null;
            oTree['prev'] = null;
            oTree['firstchild'] = null;

            // Look for children
            children = $(elTable).find("tr.form-row[childof='" + nodeid + "']");

            // Are there children?
            if (children.length > 0) {
              oTree['child'] = []
              // Walk all the children of this parent
              previous = null;
              children.each(function (idx, el) {
                var oChild;

                // Fill in the details of this child
                oChild = private_methods.sermon_tree(elTable, el);
                if (oChild !== null) {
                  // Is this the first child?
                  if (idx === 0) { oTree['firstchild'] = oChild; }
                  // Normal processing
                  oChild['parent'] = oTree;
                  oChild['prev'] = previous;
                  // Add this child to my children
                  oTree['child'].push(oChild);
                  if (previous !== null) {
                    previous['next'] = oChild;
                  }
                  // Keep track of the previous
                  previous = oChild;
                }
              });
            }
          }


          // Return the result
          return oTree;
        } catch (ex) {
          private_methods.errMsg("sermon_tree", ex);
          return null;
        }
      },

      /**
       * sermon_down
       *    Move nodeid one place down
       * 
       * @param {obj} oTree
       * @param {tr}  row
       * @returns {list}
       */
      sermon_down: function (oTree, row) {
        var sermonid = "",
            i = 0,
            child = [],
            parent = null,
            next = null,
            prev = null,
            node = null;

        try {
          // Get the sermonid in the row
          sermonid = $(row).attr("sermonid");

          // Find the sermon in the tree
          node = private_methods.sermon_node(oTree, sermonid);
          if (node !== null) {
            // We found the node with this sermon
            // Find the next sibling of this node
            next = node['next'];
            prev = node['prev'];
            if (prev !== null) {
              prev['next'] = next;
            }
            if (next !== null) {
              // There is a 'next' sibling, so we can go past it
              node['next'] = next['next'];
              next['next'] = node;
              next['prev'] = node['prev'];
              node['prev'] = next;
              // Keep track of firstchild
              if (node['prev'] === null) {
                node['parent']['firstchild'] = node;
              } else if (next['prev'] === null) {
                next['parent']['firstchild'] = next;
              }
            }
            // Re-arrange the list of children in the parent
            parent = node['parent'];
            next = parent['firstchild'];
            child = [];
            while (next !== null) {
              child.push(next);
              next = next['next'];
            }
            parent['child'] = child;
          }

          // Return the result
          return oTree;
        } catch (ex) {
          private_methods.errMsg("sermon_down", ex);
          return null;
        }
      },

      /**
       * sermon_reorder
       *    Order the surface form of the table in accordance with the tree
       * 
       * @param {obj} oTree
       * @returns {bool}
       */
      sermon_reorder: function (elTable, oTree) {
        var lst_this = [],
            prevtr = null,
            oNode = null,
            row = null,
            i = 0;

        try {
          // Get a list of nodes
          private_methods.sermon_list(oTree, lst_this);

          // Walk the list
          for (i = 0; i < lst_this.length; i++) {
            oNode = lst_this[i];
            if (prevtr === null) {
              // Is this a good one?
              if (oNode['row'] !== null) {
                // This must be the first visible child 
                // See: https://stackoverflow.com/questions/2007357/how-to-set-dom-element-as-the-first-child
                // if (elTable.firstChild !== )
              }
            }
          }

          return true;
        } catch (ex) {
          private_methods.errMsg("sermon_reorder", ex);
          return false;
        }
      },

      /**
       * sermon_list
       *    Create a list of sub nodes
       * 
       * @param {obj}  oNode
       * @parem {list} lst_this
       * @returns {bool}
       */
      sermon_list: function (oNode, lst_this) {
        var next = null,
            i = 0,
            child = [];

        try {
          // Add myself to the list
          lst_this.push(oNode)
          // Get my children
          next = oNode['firstchild'];
          while (next !== null) {
            private_methods.sermon_list(next, lst_this);
            //for (i = 0; i < child.length; i++) {
            //  lst_this.push(child[i]);
            //}
            next = next['next'];
          }
          return true;
        } catch (ex) {
          private_methods.errMsg("sermon_list", ex);
          return false;
        }
      },

      /**
       * sermon_simple
       *    Simple text representation of this node
       * 
       * @param {obj} oNode
       * @parem {int} level
       * @returns {text}
       */
      sermon_simple: function(oNode, level) {
        var lHtml = [],
            next = null,
            spaces = "";

        try {
          if (level === undefined) { level = 0; }
          // Print this node
          spaces = Array( level * 2 +1).join(" ");
          lHtml.push(spaces + oNode['sermonid'] + "\t"+ oNode['rowidx']);
          // Treat children
          next = oNode['firstchild'];
          while (next !== null) {
            lHtml.push(private_methods.sermon_simple(next, level + 1));
            next = next['next'];
          }
          return lHtml.join("\n");
        } catch (ex) {
          private_methods.errMsg("sermon_simple", ex);
        }
      },

      /**
       * sermon_node
       *    Find the node with the identified sermonid
       * 
       * @param {obj} node
       * @param {id}  sermonid
       * @returns {node}
       */
      sermon_node: function (node, sermonid) {
        var child = null,
            children = [],
            i = 0,
            response = null;

        try {
          // Validate
          if (node === null) return null;

          // Is this the one?
          if (node['sermonid'] === sermonid) {
            return node;
          }

          // Check the children
          if ('child' in node) {
            children = node['child'];
            for (i = 0; i < children.length; i++) {
              child = children[i];
              response = private_methods.sermon_node(child, sermonid);
              if (response !== null) {
                return response;
              }
            }
          }
          // Getting here means no result
          return null;
        } catch (ex) {
          private_methods.errMsg("sermon_node", ex);
          return null;
        }
      },

      /**
       * sermon_sibling
       *    Within [elTable] look for rows that are under [childof] and before [nodeid]
       * 
       * @param {el}  elTable
       * @param {int} nodeid
       * @param {int} childof
       * @returns {list}
       */
      sermon_sibling: function (elTable, nodeid, childof, order) {
        var sibling = [];

        try {
          $(elTable).find("tr.form-row[childof='" + childof + "']").each(function (idx, el) {
            var thisid = $(el).attr("nodeid");

            if (thisid !== undefined && thisid !== "") {
              switch (order) {
                case "preceding":
                  if (parseInt(thisid, 10) < nodeid) { sibling.push(el); }
                  break;
                case 'following':
                  if (parseInt(thisid, 10) > nodeid) { sibling.push(el); }
                  break;
              }
            }
          });
          return sibling;
        } catch (ex) {
          private_methods.errMsg("sermon_sibling", ex);
          return [];
        }
      },

      /**
       * sermon_exchange
       *    Make two sermons exchange place (siblings)
       * 
       * @param {el} elSrc
       * @param {el} elDst
       * @returns {bool}
       */
      sermon_exchange: function (elSrc, elDst) {
        var nodesrcid = -1,
            nodedstid = -1,
            highid = -1,
            lowid = -1,
            children = [],
            counter = 1,
            mapping = {},
            oTree = {},
            method = "new",
            elTable = null;

        try {
          // Get the table
          elTable = $(elSrc).closest("table");

          // Get the current values
          nodesrcid = parseInt($(elSrc).attr("nodeid"), 10);
          nodedstid = parseInt($(elDst).attr("nodeid"), 10);

          switch (method) {
            case "old":
              // Exchange source and destination 
              $(elSrc).attr("nodeid", nodedstid);
              $(elDst).attr("nodeid", nodesrcid);

              // Change all the children of the original source
              $(elTable).find("tr.form-row").each(function (idx, el) {
                var sNodeSrc = nodesrcid.toString(),
                    sNodeDst = nodedstid.toString();

                // Is this row a child of source?
                if ($(el).attr("childof") === sNodeSrc) {
                  $(el).attr("childof", sNodeDst);
                  children.push(el);
                } else if ($(el).attr("childof") === sNodeDst) {
                  $(el).attr("childof", sNodeSrc);
                  children.push(el);
                }
              });

              // Determine where to move
              if (nodesrcid < nodedstid) {
                // We are moving a node 'down'
                if (children.length === 0) {
                  // No children: simple moving
                  elSrc.insertAfter(elDst);
                } else {
                  // Move after the last child
                  elSrc.insertAfter(children[children.length - 1]);
                }
              } else {
                // We are moving a node 'up'
                if (children.length === 0) {
                  // No children: simple moving
                  elSrc.insertBefore(elDst);
                } else {
                  // Move before the first
                  elSrc.insertBefore(elDst);
                  // elSrc.insertBefore(children[0]);
                }
              }

              break;
            case "attempt":
              // Determine the correct interval
              if (nodesrcid < nodedstid) {
                highid = nodesrcid; lowid = nodedstid;
              } else {
                highid = nodedstid; lowid = nodesrcid;
              }

              // Determine where to move
              if (nodesrcid < nodedstid) {
                // We are moving a node 'down'
                if (children.length === 0) {
                  // No children: simple moving
                  elSrc.insertAfter(elDst);
                } else {
                  // Move after the last child
                  elSrc.insertAfter(children[children.length - 1]);
                }
              } else {
                // We are moving a node 'up'
                if (children.length === 0) {
                  // No children: simple moving
                  elSrc.insertBefore(elDst);
                } else {
                  // Move before the first
                  elSrc.insertBefore(elDst);
                  // elSrc.insertBefore(children[0]);
                }
              }

              // Treat all the rows that need it
              $(elTable).find("tr.form-row").each(function (idx, el) {
                var nodeid = parseInt($(el).attr("nodeid"), 10);

                // Find out where we should be
                counter += 1;
                // Make a mapping if needed
                if (nodeid !== counter) {
                  mapping[nodeid.toString()] = counter;
                }
              });

              // Now apply the mapping
              $(elTable).find("tr.form-row").each(function (idx, el) {
                var nodeid = $(el).attr("nodeid"),
                    childof = $(el).attr("childof");

                // Check if a mapping is needed
                if (nodeid in mapping) {
                  $(el).attr("nodeid", mapping[nodeid]);
                }
                if (childof in mapping) {
                  $(el).attr("childof", mapping[childof])
                }
                
              });

              break;
            case "new":
              // ================ TESTING ==================

              // Create a Tree from the sermons
              oTree = private_methods.sermon_tree(elTable);
              // move 
              break;
          }
          
          // Re-number the sermon list
          private_methods.sermon_renumber(elTable);

          // Return positively 
          return true
        } catch (ex) {
          private_methods.errMsg("sermon_exchange", ex);
          return false;
        }
      },

      /**
       * sermon_renumber
       *    Re-number the sermons in the list of current table rows
       * 
       * @param {el} elTable
       * @returns {bool}
       */
      sermon_renumber: function (elTable) {
        var counter = 1;

        try {
          // Get list of current hierarchy
          $(elTable).find("tr.form-row").each(function (idx, el) {
            var argnode = null;

            argnode = $(el).find(".arg-nodeid");
            if (argnode.length > 0) {
              argnode.first().text(counter++);
            }
          });
          return true;
        } catch (ex) {
          private_methods.errMsg("sermon_renumber", ex);
          return false;
        }
      },

      /**
       * sermon_hlisttree
       *    Make an object list of the current sermon hierarchy
       * 
       * @param {el} elRoot
       * @returns {bool}
       */
      sermon_hlisttree: function (elRoot) {
        var hList = [];

        try {
          $(elRoot).find("div.tree").each(function (idx, el) {
            var sermonid = "",
                nodeid = "",
                childof = "",
                oNew = {};

            sermonid = $(el).attr("sermonid");
          });

          return hList;
        } catch (ex) {
          private_methods.errMsg("sermon_hlisttree", ex);
          return [];
        }
      },

      /**
       * sermon_hlist
       *    Make an object list of the current table rows contents
       * 
       * @param {el} elTable
       * @returns {bool}
       */
      sermon_hlist: function (elTable) {
        var hList = [];

        try {
          // Get list of current hierarchy
          $(elTable).find("tr.form-row").each(function (idx, el) {
            var sermonid, nodeid, childof, oNew = {};

            sermonid = $(el).attr("sermonid");
            nodeid = $(el).attr("nodeid");
            childof = $(el).attr("childof");
            oNew = { id: sermonid, nodeid: nodeid, childof: childof };
            hList.push(oNew);
          });
          return hList;
        } catch (ex) {
          private_methods.errMsg("sermon_hlist", ex);
          return [];
        }
      },

      /**
       * screenCoordsForRect
       *    Get the correct screen coordinates for the indicated <svg> <rect> element
       * 
       * @param {el} svgRect
       * @returns {object}
       */
      screenCoordsForRect: function (svgRect) {
        var pt = null,
            elSvg = null,
            rect = null,
            oBound = {},
            matrix;

        try {
          // Get the root <svg>
          elSvg = $(svgRect).closest("svg").get(0);

          rect = svgRect.get(0);
          oBound = rect.getBoundingClientRect();

          // Take into account scrolling
          oBound['x'] += document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] += document.documentElement.scrollTop || document.body.scrollTop;
          return oBound;
        } catch (ex) {
          private_methods.errMsg("screenCoordsForRect", ex);
          return oBound;
        }

      },

      /**
       *  var_move
       *      Move variable row one step down or up
       *      This means the 'order' attribute changes
       */
      var_move: function (elStart, sDirection, sType) {
        var elRow = null,
            el = null,
            tdCounter = null,
            rowSet = null,
            iLen = 0;

        try {
          // Find out what type we have
          if (sType === undefined) { sType = ""; }
          switch (sType) {
            case "selected":
              // Find the selected row
              elRow = $(elStart).closest("form").find("tr.selected").first();
              // The element is below
              el = $(elRow).find(".var-order input").parent();
              break;
            default:
              // THe [el] is where we start
              el = elStart;
              // The row is above me
              elRow = $(el).closest("tr");
              break;
          }
          // Perform the action immediately
          switch (sDirection) {
            case "down":
              // Put the 'other' (=next) row before me
              $(elRow).next().after($(elRow));
              break;
            case "up":
              // Put the 'other' (=next) row before me
              $(elRow).prev().before($(elRow));
              break;
            default:
              return;
          }
          // Now iterate over all rows in this table
          rowSet = $(elRow).parent().children(".form-row").not(".empty-form");
          iLen = $(rowSet).length;
          $(rowSet).each(function (index, el) {
            var elInput = $(el).find(".var-order input");
            var sOrder = $(elInput).val();
            // Set the order of this element
            if (parseInt(sOrder, 10) !== index + 1) {
              $(elInput).attr("value", index + 1);
              $(elInput).val(index + 1);
              // Look for a <td> element with class "counter"
              tdCounter = $(el).find("td.counter");
              if (tdCounter.length > 0) {
                $(tdCounter).html(index+1);
              }
            }
            if (sType === "") {
              // Check visibility of up and down
              $(el).find(".var-down").removeClass("hidden");
              $(el).find(".var-up").removeClass("hidden");
              if (index === 0) {
                $(el).find(".var-up").addClass("hidden");
              }
              if (index === iLen - 1) {
                $(el).find(".var-down").addClass("hidden");
              }
            }
          });
        } catch (ex) {
          private_methods.errMsg("var_move", ex);
        }
      },
      errMsg: function (sMsg, ex, bNoCode) {
        var sHtml = "",
            bCode = true;

        // Check for nocode
        if (bNoCode !== undefined) {
          bCode = not(bNoCode);
        }
        // Replace newlines by breaks
        sMsg = sMsg.replace(/\n/g, "\n<br>");
        if (ex === undefined) {
          sHtml = "Error: " + sMsg;
        } else {
          sHtml = "Error in [" + sMsg + "]<br>" + ex.message;
        }
        sHtml = "<code>" + sHtml + "</code>";
        console.log(sHtml);
        $("#" + loc_divErr).html(sHtml);
      },
      errClear: function () {
        $("#" + loc_divErr).html("");
        loc_bExeErr = false;
      },
      mainWaitStart : function() {
        var elWait = $(".main-wait").first();
        if (elWait !== undefined && elWait !== null) {
          $(elWait).removeClass("hidden");
        }
      },
      mainWaitStop: function () {
        var elWait = $(".main-wait").first();
        if (elWait !== undefined && elWait !== null) {
          $(elWait).addClass("hidden");
        }
      },
      waitInit: function (el) {
        var elResPart = null,
            elWait = null;

        try {
          // Set waiting div
          elResPart = $(el).closest(".research_part");
          if (elResPart !== null) {
            elWait = $(elResPart).find(".research-fetch").first();
          }
          return elWait;
        } catch (ex) {
          private_methods.errMsg("waitInit", ex);
        }
      },
      waitStart: function(el) {
        if (el !== null) {
          $(el).removeClass("hidden");
        }
      },
      waitStop: function (el) {
        if (el !== null) {
          $(el).addClass("hidden");
        }
      }
    }

    // Public methods
    return {

      /**
       *  init_events
       *      Bind main necessary events
       *
       */
      init_events: function (sUrlShow) {
        var lHtml = [],
            elA = null,
            object_id = "",
            targetid = null,
            post_loads = [],
            options = {},
            sHtml = "";

        try {
          // See if there are any post-loads to do
          $(".post-load").each(function (idx, value) {
            var targetid = $(this);
            post_loads.push(targetid);
            // Remove the class
            $(targetid).removeClass("post-load");
          });

          // No closing of certain dropdown elements on clicking
          $(".dropdown-toggle").on({
            "click": function (event) {
              var evtarget = $(event.target);
              if ($(evtarget).closest(".nocloseonclick")) {
                $(this).data("closable", false);
              } else {
                $(this).data("closable", true);
              }
            }
          });

          // Now address all items from the list of post-load items
          post_loads.forEach(function (targetid, index) {
            var data = [],
                lst_ta = [],
                i = 0,
                targeturl = $(targetid).attr("targeturl");

            // Load this one with a GET action
            $.get(targeturl, data, function (response) {
              // Remove the class
              $(targetid).removeClass("post-load");

              // Action depends on the response
              if (response === undefined || response === null || !("status" in response)) {
                private_methods.errMsg("No status returned");
              } else {
                switch (response.status) {
                  case "ok":
                    // Show the result
                    $(targetid).html(response['html']);
                    // Call initialisation again
                    ru.passim.seeker.init_events(sUrlShow);
                    // Handle type aheads
                    if ("typeaheads" in response) {
                      // Perform typeahead for these ones
                      ru.passim.init_event_listeners(response.typeaheads);
                    }
                    break;
                  case "error":
                    // Show the error
                    if ('msg' in response) {
                      $(targetid).html(response.msg);
                    } else {
                      $(targetid).html("An error has occurred (passim.seeker post_loads)");
                    }
                    break;
                }
              }

            });
          });

          //options = { "templateSelection": ru.passim.ssg_template };
          //$(".django-select2.select2-ssg").djangoSelect2(options);
          //$(".django-select2.select2-ssg").select2({
          //  templateSelection: ru.passim.ssg_template
          //});
          //$(".django-select2.select2-ssg").on("select2:select", function (e) {
          //  var sId = $(this).val(),
          //      sText = "",
          //      sHtml = "",
          //      idx = 0,
          //      elOption = null,
          //      elRendered = null;

          //  elRendered = $(this).parent().find(".select2-selection__rendered");
          //  sHtml = $(elRendered).html();
          //  idx = sHtml.indexOf("</span>");
          //  if (idx > 0) {
          //    idx += 7;
          //    sText = sHtml.substring(idx);
          //    if (sText.length > 50) {
          //      sText = sText.substring(0, 50) + "...";
          //      sHtml = sHtml.substring(0, idx) + sText;
          //      $(elRendered).html(sHtml);
          //    }
          //  }
          //});

          // NOTE: only treat the FIRST <a> within a <tr class='add-row'>
          $("tr.add-row").each(function () {
            elA = $(this).find("a").first();
            $(elA).unbind("click");
            $(elA).click(ru.passim.seeker.tabular_addrow);
          });
          // Bind one 'tabular_deletrow' event handler to clicking that button
          $(".delete-row").unbind("click");
          $('tr td a.delete-row').click(ru.passim.seeker.tabular_deleterow);

          // Bind the click event to all class="ajaxform" elements
          $(".ajaxform").unbind('click').click(ru.passim.seeker.ajaxform_click);

          $(".ms.editable a").unbind("click").click(ru.passim.seeker.manu_edit);
          $(".srm.editable a").unbind("click").click(ru.passim.seeker.sermo_edit);

          // Show URL if needed
          if (loc_urlStore !== undefined && loc_urlStore !== "") {
            // show it
            window.location.href = loc_urlStore;
          } else if (sUrlShow !== undefined && sUrlShow !== "") {
            // window.location.href = sUrlShow;
            // history.pushState(null, null, sUrlShow);
          }

          // Set handling of unique-field
          $("td.unique-field input").unbind("change").change(ru.passim.seeker.unique_change);

          // Make sure typeahead is re-established
          ru.passim.init_event_listeners();
          ru.passim.init_typeahead();

          // Switch filters
          $(".badge.filter").unbind("click").click(ru.passim.seeker.filter_click);

          // Make modal draggable
          $(".modal-header, modal-dragpoint").on("mousedown", function (mousedownEvt) {
            var $draggable = $(this),
                x = mousedownEvt.pageX - $draggable.offset().left,
                y = mousedownEvt.pageY - $draggable.offset().top;

            $("body").on("mousemove.draggable", function (mousemoveEvt) {
              $draggable.closest(".modal-dialog").offset({
                "left": mousemoveEvt.pageX - x,
                "top": mousemoveEvt.pageY - y
              });
            });
            $("body").one("mouseup", function () {
              $("body").off("mousemove.draggable");
            });
            $draggable.closest(".modal").one("bs.modal.hide", function () {
              $("body").off("mousemove.draggable");
            });
          });

          //// Any other draggables
          //$(".draggable").draggable({
          //  cursor: "move",
          //  snap: ".draggable",
          //  snapMode: "inner",
          //  snapTolerance: 20
          //});


        } catch (ex) {
          private_methods.errMsg("init_events", ex);
        }
      },

      sermon_drag: function (ev) {
        var elTree = null,
            divId = "",
            sermonid = "";
        try {
          elTree = $(ev.target).closest(".tree");
          sermonid = $(elTree).attr("sermonid");
          divId = $(elTree).attr("id");

          ev.dataTransfer.setData("text", divId);
        } catch (ex) {
          private_methods.errMsg("sermon_drag", ex);
        }
      },

      sermon_dragenter: function (ev) {
        var elTree = null, sermonid = "";
        try {
          ev.preventDefault();
          if (ev.target.nodeName.toLowerCase() === "td" && $(ev.target).hasClass("ruler")) {
            //$(ev.target).addClass("dragover");
            $(ev.target).addClass("ruler_black");
            $(ev.target).removeClass("ruler_white");
            // make row larger
            $(ev.target).parent().addClass("ruler_show");
          } else {
            $(ev.target).closest("td").addClass("dragover");
            $(ev.target).addClass("dragover");
          }
        } catch (ex) {
          private_methods.errMsg("sermon_dragenter", ex);
        }
      },

      sermon_dragleave: function (ev) {
        var elTree = null, sermonid = "";
        try {
          $("#sermon_tree .dragover").removeClass("dragover");
          $("#sermon_tree .ruler").removeClass("ruler_black");
          $("#sermon_tree .ruler").addClass("ruler_white");
          $("#sermon_tree .ruler_show").removeClass("ruler_show");
        } catch (ex) {
          private_methods.errMsg("sermon_dragleave", ex);
        }
      },

      sermon_drop: function (ev) {
        var elTree = null,
            divSrcId = "",
            divDstId = "",
            divSrc = null,
            divDst = null,
            level = 0,
            target_under_source = false,
            type = "under",
            sermonid = "";
        try {
          // Prevent default handling
          ev.preventDefault();

          // Figure out what the source and destination is
          elTree = $(ev.target).closest(".tree");
          divSrcId = ev.dataTransfer.getData("text");
          divDstId = $(elTree).attr("id");

          // Reset the class of the drop element
          $("#sermon_tree .dragover").removeClass("dragover");
          $("#sermon_tree .ruler").removeClass("ruler_black");
          $("#sermon_tree .ruler").addClass("ruler_white");
          $("#sermon_tree .ruler_show").removeClass("ruler_show");

          // Find the actual source div
          divSrc = $("#sermon_tree").find("#" + divSrcId);
          // The destination - that is me myself
          divDst = elTree;

          // Do we need to put the source "under" the destination or "before" it?
          if ($(ev.target).hasClass("ruler")) {
            type = "before";
          }

          // Action now depends on the type
          switch (type) {
            case "under":   // Put src under div dst
              // check for target under source -- that is not allowed
              target_under_source = ($(divSrc).find("#" + divDstId).length > 0);

              // Check if the target is okay to go to
              if (divSrcId !== divDstId && !target_under_source) {

                // Show source and destination
                console.log("Move from " + divSrcId + " to UNDER " + divDstId);
                $("#sermonlog").html("Move from " + divSrcId + " to UNDER " + divDstId);

                // Move source *UNDER* the destination
                divDst.append(divSrc);
                // Get my dst level
                level = parseInt($(divDst).attr("level"), 10);
                level += 1;
                $(divSrc).attr("level", level.toString());
              } else {
                $("#sermonlog").html("not allowed to move from " + divSrcId + " to UNDER " + divDstId);
              }
              break;
            case "before":  // Put src before div dst
              // Validate
              if (divSrcId === divDstId) {
                $("#sermonlog").html("Cannot move me " + divSrcId + " before myself " + divDstId);
              } else {
                // Move source *BEFORE* the destination
                divSrc.insertBefore(divDst);
                // Adapt my level to the one before me
                $(divSrc).attr("level", $(divDst).attr("level"));
                // Show what has been done
                $("#sermonlog").html("Move " + divSrcId + " to BEFORE " + divDstId);
              }
              break;
          }
        } catch (ex) {
          private_methods.errMsg("sermon_drop", ex);
        }
      },



      /**
       * unique_change
       *    Make sure only one input box is editable
       *
       */
      init_select2: function (elName) {
        var select2_options = null,
            i = 0,
            elDiv = "#" + elName,
            oRow = null;

        try {
          for (i = 0; i < lAddTableRow.length; i++) {
            oRow = lAddTableRow[i];
            if (oRow['table'] === elName) {
              if ("select2_options" in oRow) {
                select2_options = oRow['select2_options'];
                // Remove previous .select2
                $(elDiv).find(".select2").remove();
                // Execute djangoSelect2()
                $(elDiv).find(".django-select2").djangoSelect2(select2_options);
                return true;
              }
            }
          }
          return false;
        } catch (ex) {
          private_methods.errMsg("init_select2", ex);
          return false;
        }
      },

      /**
       * unique_change
       *    Make sure only one input box is editable
       *
       */
      unique_change: function () {
        var el = $(this),
            elTr = null;

        try {
          elTr = $(el).closest("tr");
          $(elTr).find("td.unique-field").find("input").each(function (idx, elInput) {
            if ($(el).attr("id") !== $(elInput).attr("id")) {
              $(elInput).prop("disabled", true);
            }
          });
  
        } catch (ex) {
          private_methods.errMsg("unique_change", ex);
        }
      },

      /**
       * filter_click
       *    What happens when clicking a badge filter
       *
       */
      filter_click: function (el) {
        var target = null,
            specs = null;

        try {
          target = $(this).attr("targetid");
          if (target !== undefined && target !== null && target !== "") {
            target = $("#" + target);
            // Action depends on checking or not
            if ($(this).hasClass("on")) {
              // it is on, switch it off
              $(this).removeClass("on");
              $(this).removeClass("jumbo-3");
              $(this).addClass("jumbo-1");
              // Must hide it and reset target
              $(target).addClass("hidden");

              // Check if target has a targetid
              specs = $(target).attr("targetid");
              if (specs !== undefined && specs !== "") {
                // Reset related badges
                $(target).find("span.badge").each(function (idx, elThis) {
                  var subtarget = "";

                  $(elThis).removeClass("on");
                  $(elThis).removeClass("jumbo-3");
                  $(elThis).removeClass("jumbo-2");
                  $(elThis).addClass("jumbo-1");
                  subtarget = $(elThis).attr("targetid");
                  if (subtarget !== undefined && subtarget !== "") {
                    $("#" + subtarget).addClass("hidden");
                  }
                });
                // Re-define the target
                target = $("#" + specs);
              } 

              $(target).find("input").each(function (idx, elThis) {
                $(elThis).val("");
              });
              // Also reset all select 2 items
              $(target).find("select").each(function (idx, elThis) {
                $(elThis).val("").trigger("change");
              });

            } else {
              // Must show target
              $(target).removeClass("hidden");
              // it is off, switch it on
              $(this).addClass("on");
              $(this).removeClass("jumbo-1");
              $(this).addClass("jumbo-3");
            }

          }
        } catch (ex) {
          private_methods.errMsg("filter_click", ex);
        }
      },

      /**
       * add_new_select2
       *    Show [table_new] element
       *
       */
      add_new_select2: function (el) {
        var elTr = null,
            elRow = null,
            options = {},
            elDiv = null;

        try {
          elTr = $(el).closest("tr");           // Nearest <tr>
          elDiv = $(elTr).find(".new-mode");    // The div with new-mode in it
          // Show it
          $(elDiv).removeClass("hidden");
          // Find the first row
          elRow = $(elDiv).find("tbody tr").first();
          options['select2'] = true;
          ru.passim.seeker.tabular_addrow($(elRow), options);

          // Add
        } catch (ex) {
          private_methods.errMsg("add_new_select2", ex);
        }
      },

      /**
       * form_row_select
       *    By selecting this slement, the whole row gets into the 'selected' state
       *
       */
      form_row_select: function (elStart) {
        var elTable = null,
          elRow = null, // The row
          iSelCount = 0, // Number of selected rows
          elHier = null,
          bSelected = false;

        try {
          // Get to the row
          elRow = $(elStart).closest("tr.form-row");
          // Get current state
          bSelected = $(elRow).hasClass("selected");
          // FInd nearest table
          elTable = $(elRow).closest("table");
          // Check if anything other than me is selected
          iSelCount = 1;
          // Remove all selection
          $(elTable).find(".form-row.selected").removeClass("selected");
          elHier = $("#sermon_hierarchy");
          // CHeck what we need to do
          if (bSelected) {
            // We are de-selecting: hide the 'Up' and 'Down' buttons if needed
            // ru.cesar.seeker.show_up_down(this, false);
            $(elHier).removeClass("in");
            $(elHier).hide()
          } else {
            // Make a copy of the tree as it is
            $("#sermon_tree_copy").html($("#sermon_tree").html());
            // Select the new row
            $(elRow).addClass("selected");
            // SHow the 'Up' and 'Down' buttons if needed
            // ru.cesar.seeker.show_up_down(this, true);
            // document.getElementById('sermon_manipulate').submit();
            $(elHier).addClass("in");
            $(elHier).show();
          }

        } catch (ex) {
          private_methods.errMsg("form_row_select", ex);
        }
      },

      /**
       *  sermon_move
       *      Move the selected row
       *
       */
      sermon_move: function (type) {
        var elRoot = null,
            elSrc = null,
            elDst = null,
            elStart = null,
            elTable = null,
            elRow = null,
            elRowRef = null,
            data = [],
            sibling = [],
            oTree = null,
            targeturl = "",
            sText = "",
            method = "dom",   //
            hList = [],       // List of current hierarchy
            dst = -1,         // Target count
            sermonid = "",    // The sermonid of the selected one
            nodeid = -1,
            nodedstid = -1,
            level = -1,
            childof = -1;

        try {
          // Make sure we know where the DOM is
          elRoot = $("#sermon_tree");

          // Determine which row is selected
          elStart = $("#sermon_list").find("tr.selected > td.selectable").first();
          elRow = $(elStart).parent();
          elTable = $(elRow).closest("table");
          sermonid = $(elRow).attr("sermonid");

          // Action depends on the type
          switch (type) {
            case "close": // Close the modal
              ru.passim.seeker.form_row_select(elStart);
              // Return the stored copy
              $("#sermon_tree").html($("#sermon_tree_copy").html());
              // Make sure the tree is redrawn
              ru.passim.seeker.sermon_drawtree();
              break;
            case "up":    // position me before my preceding sibling
              // Get the <div> that should be moved
              elSrc = $(elRoot).find("div.tree[sermonid={0}]".format(sermonid)).first();
              // See if we have a preceding sibling
              elDst = $(elSrc).prev("div.tree");
              if (elDst.length > 0) {
                $(elSrc).insertBefore(elDst);
                // Make sure the tree is redrawn
                ru.passim.seeker.sermon_drawtree(sermonid);
              }

              break;
            case "down":  // position me after my following sibling
              // Get the <div> that should be moved
              elSrc = $(elRoot).find("div.tree[sermonid={0}]".format(sermonid)).first();
              // See if we have a following sibling
              elDst = $(elSrc).next("div.tree");
              if (elDst.length > 0) {
                $(elSrc).insertAfter(elDst);
                // Make sure the tree is redrawn
                ru.passim.seeker.sermon_drawtree(sermonid);
              }

              break;
            case "left":  // let me become a child of my grandparent, positioned AFTER my parent
              // Get the <div> that should be moved
              elSrc = $(elRoot).find("div.tree[sermonid={0}]".format(sermonid)).first();
              // See if there is a parent after which I can be placed
              elDst = $(elSrc).parent("div.tree");
              if (elDst.length > 0) {
                // There is a parent: put me after it
                $(elSrc).insertAfter(elDst);
                // Change the level
                level = parseInt($(elSrc).attr("level"), 10);
                $(elSrc).attr("level", level - 1);
                // Make sure the tree is redrawn
                ru.passim.seeker.sermon_drawtree(sermonid);
              }
              break;
            case "right":  // let me become a child of my preceding SIBLING
              // Get the <div> that should be moved
              elSrc = $(elRoot).find("div.tree[sermonid={0}]".format(sermonid)).first();
              // See if there is a preceding sibling
              elDst = $(elSrc).prev("div.tree");
              if (elDst.length > 0) {
                // There is a preceding sibling: make me into its child
                $(elDst).append(elSrc);
                // Change the level
                level = parseInt($(elSrc).attr("level"), 10);
                $(elSrc).attr("level", level + 1);
                // Make sure the tree is redrawn
                ru.passim.seeker.sermon_drawtree(sermonid);
              }
              break;
            case "save":  // Get an adapted list of the hierarchy, post to the server and receive response
              // Get list of current hierarchy
              //hList = private_methods.sermon_hlisttree(elRoot);
              ///*
              hList = private_methods.sermon_hlist(elTable);
              // Set the <input> value to return the contents of [hList]
              $("#id_manu-hlist").val(JSON.stringify(hList));
              // Send it onwards
              $("#save_new_hierarchy").submit();
              // */
              break;
          }

        } catch (ex) {
          private_methods.errMsg("sermon_move", ex);
        }
      },

      /**
       *  sermon_drawtree
       *      Copy the list of sermons to the div with id=sermon_tree
       *
       */
      sermon_drawtree: function (sermonid) {
        var elRoot = null,
            elTable = null;

        try {
          elTable = $("#sermon_list");
          elRoot = $("#sermon_tree");
          // Create the tree from [elTable] to [elRoot]
          private_methods.sermon_treetotable(elRoot, elTable, sermonid);

        } catch (ex) {
          private_methods.errMsg("sermon_drawtree", ex);
        }
      },

      /**
       *  sermon_level
       *      Open or close the current level in the sermon tree
       *
       */
      sermon_level: function (elThis) {
        var elChild = null,
            elTree = null,
            elTable = null;

        try {
          // Get my tree part
          elTree = $(elThis).closest(".tree");
          // Get my first child
          elChild = $(elTree).children(".tree").first();
          // Action depends on hidden or not
          if ($(elChild).hasClass("hidden")) {
            // Show
            $(elTree).children(".tree").removeClass("hidden");
          } else {
            // Hide
            $(elTree).children(".tree").addClass("hidden");
          }

        } catch (ex) {
          private_methods.errMsg("sermon_level", ex);
        }
      },

      /**
       * do_get
       *    Perform a $.get() based on the information in DOM element with id sId
       *
       */
      do_get: function (sId, func_after) {
        var elStart = null,
            data = [],
            targeturl = "",
            targetid = null;

        try {
          // Retrieve the information
          elStart = $("#" + sId);
          targeturl = $(elStart).attr("targeturl");
          targetid = $(elStart).attr("targetid");
          if (targetid === undefined || targetid === "") {targetid = sId;}
          if (targetid !== "") { targetid = "#" + targetid;}

          // Load this one with a GET action
          $.get(targeturl, data, function (response) {
            // Perform any function defined after receiving the response from the host
            if (func_after !== undefined) {
              func_after();
            }

            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ok":
                  // Show the result
                  $(targetid).html(response['html']);
                  // Call initialisation again
                  ru.passim.seeker.init_events(sUrlShow);
                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $(targetid).html(response.msg);
                  } else {
                    $(targetid).html("An error has occurred (passim.seeker do_get)");
                  }
                  break;
              }
            }

          });

        } catch (ex) {
          private_methods.errMsg("do_get", ex);
        }
      },

      /**
       * do_basket
       *    Perform a basket action
       *
       */
      do_basket: function (elStart) {
        var frm = null,
            targeturl = "",
            redirecturl = "",
            operation = "",
            targetid = "",
            colladdid = "#colladdinterface",
            basketwait = "#basket_waiting",
            basketreport = "#basket_report",
            basketlink = "#basket_coll_link",
            target = null,
            data = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Get the data from the form
          data = frm.serializeArray();
          // The url is in the ajaxurl
          targeturl = $(elStart).attr("ajaxurl");
          // Get the operation
          operation = $(elStart).attr("operation");
          // Get the targetid
          targetid = $(elStart).attr("targetid");
          // Basket report is normally hidden
          $(basketreport).addClass("hidden");

          switch (operation) {
            case "colladdstart":
              $(colladdid).removeClass("hidden");
              return;
              break;
            case "colladdcancel":
              $(colladdid).addClass("hidden");
              return;
              break;
            default:
              $(colladdid).addClass("hidden");
              break;
          }

          // validation
          if (targeturl === undefined || targeturl === "" || operation === undefined || operation === "" ||
              targetid === undefined || targetid === "") { return; }

          // Where to go to 
          target = $('#' + targetid);

          // Add operation to data
          data.push({ "name": "operation", "value": operation });

          // Show we are waiting
          $(basketwait).removeClass("hidden");

          // Call the ajax POST method
          // Issue a post
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should we do redirection?
                  if ("redirecturl" in response && response.redirecturl !== "") {
                    redirecturl = response.redirecturl;
                    window.location.href = redirecturl;
                  }
                  // Show the HTML target
                  $(target).html(response['html']);
                  // Possibly do some initialisations again??

                  // Hide the colladd interface
                  $(colladdid).addClass("hidden");

                  // Show we are no longer waiting
                  $(basketwait).addClass("hidden");

                  // Possibly show a report
                  switch (operation) {
                    case "colladd":
                      // Add the correct parameters to the report
                      $(basketlink).attr("href", response.collurl);
                      $(basketlink).html("<span>" + response.collname + "</span>");
                      // Show the report
                      $(basketreport).removeClass("hidden");
                      break;
                  }

                  // Make sure events are re-established
                  ru.passim.seeker.init_events();
                  // ru.passim.init_typeahead();

                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $(target).html(response.msg);
                  } else {
                    $(target).html("An error has occurred (passim.seeker do_basket)");
                  }
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("do_basket", ex);
        }
      },

      /**
       * search_reset
       *    Clear the information in the form's fields and then do a submit
       *
       */
      search_reset: function (elStart) {
        var frm = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Clear the information in the form's INPUT fields
          $(frm).find("input:not([readonly]).searching").val("");
          // Show we are waiting
          $("#waitingsign").removeClass("hidden");
          // Now submit the form
          frm.submit();
        } catch (ex) {
          private_methods.errMsg("search_reset", ex);
        }
      },

      /**
       * search_clear
       *    No real searching, just reset the criteria
       *
       */
      search_clear: function (elStart) {
        var frm = null,
            idx = 0,
            lFormRow = [];

        try {
          // Clear filters
          $(".badge.filter").each(function (idx, elThis) {
            var target;

            target = $(elThis).attr("targetid");
            if (target !== undefined && target !== null && target !== "") {
              target = $("#" + target);
              // Action depends on checking or not
              if ($(elThis).hasClass("on")) {
                // it is on, switch it off
                $(elThis).removeClass("on");
                $(elThis).removeClass("jumbo-3");
                $(elThis).addClass("jumbo-1");
                // Must hide it and reset target
                $(target).addClass("hidden");
                $(target).find("input").each(function (idx, elThis) {
                  $(elThis).val("");
                });
                // Also reset all select 2 items
                $(target).find("select").each(function (idx, elThis) {
                  $(elThis).val("").trigger("change");
                });
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("search_clear", ex);
        }
      },

      /**
       * search_start
       *    Gather the information in the form's fields and then do a submit
       *
       */
      search_start: function (elStart, method, iPage, sOrder) {
        var frm = null,
            url = "",
            targetid = null,
            targeturl = "",
            data = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Get the data from the form
          data = frm.serializeArray();

          // Determine the method
          if (method === undefined) { method = "submit";}

          // Get the URL from the form
          url = $(frm).attr("action");

          // Action depends on the method
          switch (method) {
            case "submit":
              // Show we are waiting
              $("#waitingsign").removeClass("hidden");
              // Store the current URL
              loc_urlStore = url;
              // If there is a page number, we need to process it
              if (iPage !== undefined) {
                $(elStart).find("input[name=page]").each(function (el) {
                  $(this).val(iPage);
                });
              }
              // If there is a sort order, we need to process it
              if (sOrder !== undefined) {
                $(elStart).find("input[name=o]").each(function (el) {
                  $(this).val(sOrder);
                });
              }
              // Now submit the form
              frm.submit();
              break;
            case "post":
              // Determine the targetid
              targetid = $(elStart).attr("targetid");
              if (targetid == "subform") {
                targetid = $(elStart).closest(".subform");
              } else {
                targetid = $("#" + targetid);
              }
              // Get the targeturl
              targeturl = $(elStart).attr("targeturl");

              // Get the page we need to go to
              if (iPage === undefined) { iPage = 1; }
              data.push({ 'name': 'page', 'value': iPage });
              if (sOrder !== undefined) {
                data.push({ 'name': 'o', 'value': sOrder });
              }

              // Issue a post
              $.post(targeturl, data, function (response) {
                // Action depends on the response
                if (response === undefined || response === null || !("status" in response)) {
                  private_methods.errMsg("No status returned");
                } else {
                  switch (response.status) {
                    case "ready":
                    case "ok":
                      // Show the HTML target
                      $(targetid).html(response['html']);
                      // Possibly do some initialisations again??

                      // Make sure events are re-established
                      // ru.passim.seeker.init_events();
                      ru.passim.init_typeahead();
                      break;
                    case "error":
                      // Show the error
                      if ('msg' in response) {
                        $(targetid).html(response.msg);
                      } else {
                        $(targetid).html("An error has occurred (passim.seeker search_start)");
                      }
                      break;
                  }
                }
              });


              break;
          }

        } catch (ex) {
          private_methods.errMsg("search_start", ex);
        }
      },

      /**
       * search_paged_start
       *    Perform a simple 'submit' call to search_start
       *
       */
      search_paged_start: function(iPage) {
        var elStart = null;

        try {
          // And then go to the first element within the form that is of any use
          elStart = $(".search_paged_start").first();
          ru.passim.seeker.search_start(elStart, 'submit', iPage)
        } catch (ex) {
          private_methods.errMsg("search_paged_start", ex);
        }
      },

      /**
       * search_ordered_start
       *    Perform a simple 'submit' call to search_start
       *
       */
      search_ordered_start: function (order) {
        var elStart = null;

        try {
          // And then go to the first element within the form that is of any use
          elStart = $(".search_ordered_start").first();
          ru.passim.seeker.search_start(elStart, 'submit', 1, order)
        } catch (ex) {
          private_methods.errMsg("search_ordered_start", ex);
        }
      },

      /**
       * gold_search_prepare
       *    Prepare the modal form to search for gold-sermon destinations
       *
       */
      gold_search_prepare: function (elStart) {
        var targetid = "",
            data = [],
            targeturl = "";

        try {
          // Set our own location
          loc_goldlink_td = $(elStart).closest("td");
          // Get the target url and the target id
          targeturl = $(elStart).attr("targeturl");
          targetid = $(elStart).attr("targetid");
          // Show the waiting signal at the targetid
          $("#" + targetid).html(loc_sWaiting);
          // Fetch and show the targeturl
          $.get(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ok":
                  // Show the result
                  $("#" + targetid).html(response['html']);
                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $("#" + targetid).html(response.msg);
                  } else {
                    $("#" + targetid).html("An error has occurred (passim.seeker gold_search_prepare)");
                  }
                  break;
              }
              // Make sure events are re-established
              // ru.passim.seeker.init_events();
              ru.passim.init_typeahead();
            }

          });

        } catch (ex) {
          private_methods.errMsg("gold_search_prepare", ex);
        }
      },

      /**
       * gold_select_save
       *    When a gold sermon has been chosen as destination link, make sure it is shown in the list
       *
       */
      gold_select_save: function (elStart) {
        var elResults = "#goldselect_results",
            elSelect = null,
            gold_html = "",
            gold_equal = "",
            gold_id = "";

        try {
          // Find out which one has been selected
          elSelect = $(elResults).find("tr.selected").first();
          gold_id = $(elSelect).find("td.gold-id").text();
          gold_html = $(elSelect).find("td.gold-text").html();
          // Set the items correctly in loc_goldlink_td
          $(loc_goldlink_td).find("input").val(gold_id);
          $(loc_goldlink_td).find(".view-mode").first().html(gold_html);
          $(loc_goldlink_td).find(".edit-mode").first().html(gold_html);

          // Remove the selection
          //$(elResults).find("tr.selected").find(".selected").removeClass("selected");

        } catch (ex) {
          private_methods.errMsg("gold_select_save", ex);
        }
      },

      /**
       * gold_page
       *    Make sure we go to the indicated page
       * 
       * @param {type} iPage
       * @param {type} sFormDiv
       */
      gold_page: function (iPage, sFormDiv) {
        var elStart = null;

        try {
          elStart = $("#" + sFormDiv);
          ru.passim.seeker.search_start(elStart, "post", iPage);
        } catch (ex) {
          private_methods.errMsg("gold_page", ex);
        }
      },

      /**
       * check_progress
       *    Check the progress of reading e.g. codices
       *
       */
      check_progress: function (progrurl, sTargetDiv) {
        var elTarget = "#" + sTargetDiv,
            sMsg = "",
            lHtml = [];

        try {
          $(elTarget).removeClass("hidden");
          // Call the URL
          $.get(progrurl, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "finished":
                  // NO NEED for further action
                  //// Indicate we are ready
                  //$(elTarget).html("READY");
                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $(elTarget).html(response.msg);
                  } else {
                    $(elTarget).html("An error has occurred (passim.seeker check_progress)");
                  }                  
                  break;
                default:
                  if ("msg" in response) { sMsg = response.msg; }
                  // Combine the status
                  sMsg = "<tr><td>" + response.status + "</td><td>" + sMsg + "</td></tr>";
                  // Check if it is on the stack already
                  if ($.inArray(sMsg, loc_progr) < 0) {
                    loc_progr.push(sMsg);
                  }
                  // Combine the status HTML
                  sMsg = "<div style=\"max-height: 200px; overflow-y: scroll;\"><table>" + loc_progr.reverse().join("\n") + "</table></div>";
                  $(elTarget).html(sMsg);
                  // Make sure we check again
                  window.setTimeout(function () { ru.passim.seeker.check_progress(progrurl, sTargetDiv); }, 200);
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("check_progress", ex);
        }
      },

      /**
       * hide
       *   Hide element [sHide] and 
       *
       */
      hide: function (sHide) {
        try {
          $("#" + sHide).addClass("hidden");
        } catch (ex) {
          private_methods.errMsg("hide", ex);
        }
      },

      /**
       * select_row
       *   Select one row in a table
       *
       */
      select_row: function (elStart, method, id) {
        var tbl = null,
            elsubform = null,
            eltowards = null,
            sSermon = "",
            select_id = "";

        try {
          // Get the table
          tbl = $(elStart).closest("table");
          // Deselect all other rows
          $(tbl).children("tbody").children("tr").removeClass("selected");
          // Select my current row
          $(elStart).addClass("selected");

          // Determine the select id: the id of the selected target
          if (id !== undefined && id !== "") {
            select_id = id;
          }

          // Determine the element in [sermongoldlink_info.html] where we need to change something
          elsubform = $(elStart).closest("div .subform");
          if (elsubform !== null && elsubform !== undefined) {
            eltowards = $(elsubform).attr("towardsid");
            if (eltowards === undefined) {
              eltowards = null;
            } else {
              eltowards = $("#" + eltowards);
            }
          }

          // Action depends on the method
          switch (method) {
            case "gold_link":
              // Select the correct gold sermon above
              if (eltowards !== null && $(eltowards).length > 0) {
                // Set the text of this sermon
                sSermon = $(elStart).find("td").last().html();
                $(eltowards).find(".edit-mode").first().html(sSermon);

                // Set the id of this sermon
                // DOESN'T EXIST!!! $(eltowards).find("#id_glink-dst").val(select_id.toString());
              }
              break;
          }
        } catch (ex) {
          private_methods.errMsg("select_row", ex);
        }
      },

      /**
       * import_data
       *   Allow user to upload a file
       *
       * Assumptions:
       * - the [el] contains parameter  @targeturl
       * - there is a div 'import_progress'
       * - there is a div 'id_{{ftype}}-{{forloop.counter0}}-file_source'
       *   or one for multiple files: 'id_files_field'
       *
       */
      import_data: function (sKey) {
        var frm = null,
            targeturl = "",
            options = {},
            fdata = null,
            el = null,
            elProg = null,    // Progress div
            elErr = null,     // Error div
            progrurl = null,  // Any progress function to be called
            data = null,
            xhr = null,
            files = null,
            sFtype = "",      // Type of function (cvar, feat, cond)
            elWait = null,
            bDoLoad = false,  // Need to load with a $.get() afterwards
            elInput = null,   // The <input> element with the files
            more = {},        // Additional (json) data to be passed on (from form-data)
            sTargetDiv = "",  // The div where the uploaded reaction comes
            sSaveDiv = "",    // Where to go if saving is needed
            sMsg = "";

        try {
          // The element to use is the key + import_info
          el = $("#" + sKey + "-import_info");
          elProg = $("#" + sKey + "-import_progress");
          elErr = $("#" + sKey + "-import_error");

          // Set the <div> to be used for waiting
          elWait = private_methods.waitInit(el);

          // Get the URL
          targeturl = $(el).attr("targeturl");
          progrurl = $(el).attr("sync-progress");
          sTargetDiv = $(el).attr("targetid");
          sSaveDiv = $(el).attr("saveid");

          if (targeturl === undefined && sSaveDiv !== undefined && sSaveDiv !== "") {
            targeturl = $("#" + sSaveDiv).attr("ajaxurl");
            sTargetDiv = $("#" + sSaveDiv).attr("openid");
            sFtype = $(el).attr("ftype");
            bDoLoad = true;
          }

          if ($(el).is("input")) {
            elInput = el;
          } else {
            elInput = $(el).find("input").first();
          }

          // Show progress
          $(elProg).attr("value", "0");
          $(elProg).removeClass("hidden");
          if (bDoLoad) {
            $(".save-warning").html("loading the definition..." + loc_sWaiting);
            $(".submit-row button").prop("disabled", true);
          }

          // Add data from the <form> nearest to me: 
          frm = $(el).closest("form");
          if (frm !== undefined) { data = $(frm).serializeArray(); }

          for (var i = 0; i < data.length; i++) {
            more[data[i]['name']] = data[i]['value'];
          }
          // Showe the user needs to wait...
          private_methods.waitStart(elWait);

          // Now initiate any possible progress calling
          if (progrurl !== null) {
            loc_progr = [];
            window.setTimeout(function () { ru.passim.seeker.check_progress(progrurl, sTargetDiv); }, 2000);
          }

          // Upload XHR
          $(elInput).upload(targeturl,
            more,
            function (response) {
              // Transactions have been uploaded...
              console.log("done: ", response);

              // Show where we are
              $(el).addClass("hidden");
              $(".save-warning").html("saving..." + loc_sWaiting);

              // First leg has been done
              if (response === undefined || response === null || !("status" in response)) {
                private_methods.errMsg("No status returned");
              } else {
                switch (response.status) {
                  case "ok":
                    // Check how we should react now
                    if (bDoLoad) {
                      // Show where we are
                      $(".save-warning").html("retrieving..." + loc_sWaiting);

                      $.get(targeturl, function (response) {
                        if (response === undefined || response === null || !("status" in response)) {
                          private_methods.errMsg("No status returned");
                        } else {
                          switch (response.status) {
                            case "ok":
                              // Show the response in the appropriate location
                              $("#" + sTargetDiv).html(response.html);
                              $("#" + sTargetDiv).removeClass("hidden");
                              break;
                            default:
                              // Check how/what to show
                              if ("err_view" in response) {
                                private_methods.errMsg(response['err_view']);
                              } else if ("error_list" in response) {
                                private_methods.errMsg(response['error_list']);
                              } else {
                                // Just show the HTML
                                $("#" + sTargetDiv).html(response.html);
                                $("#" + sTargetDiv).removeClass("hidden");
                              }
                              break;
                          }
                          // Make sure events are in place again
                          ru.passim.seeker.init_events();
                          switch (sFtype) {
                            case "cvar":
                              ru.passim.seeker.init_cvar_events();
                              break;
                            case "cond":
                              ru.passim.seeker.init_cond_events();
                              break;
                            case "feat":
                              ru.passim.seeker.init_feat_events();
                              break;
                          }
                          // Indicate we are through with waiting
                          private_methods.waitStop(elWait);
                        }
                      });
                    } else {
                      // Remove all project-part class items
                      $(".project-part").addClass("hidden");
                      // Place the response here
                      $("#" + sTargetDiv).html(response.html);
                      $("#" + sTargetDiv).removeClass("hidden");
                    }
                    break;
                  default:
                    // Check WHAT to show
                    sMsg = "General error (unspecified)";
                    if ("err_view" in response) {
                      sMsg = response['err_view'];
                    } else if ("error_list" in response) {
                      sMsg = response['error_list'];
                    } else {
                      // Indicate that the status is not okay
                      sMsg = "Status is not good. It is: " + response.status;
                    }
                    // Show the message at the appropriate location
                    $(elErr).html("<div class='error'>" + sMsg + "</div>");
                    // Make sure events are in place again
                    ru.passim.seeker.init_events();
                    switch (sFtype) {
                      case "cvar":
                        ru.passim.seeker.init_cvar_events();
                        break;
                      case "cond":
                        ru.passim.seeker.init_cond_events();
                        break;
                      case "feat":
                        ru.passim.seeker.init_feat_events();
                        break;
                    }
                    // Indicate we are through with waiting
                    private_methods.waitStop(elWait);
                    $(".save-warning").html("(not saved)");
                    break;
                }
              }
              private_methods.waitStop(elWait);
            }, function (progress, value) {
              // Show  progress of uploading to the user
              console.log(progress);
              $(elProg).val(value);
            }
          );
          // Hide progress after some time
          setTimeout(function () { $(elProg).addClass("hidden"); }, 1000);

          // Indicate waiting can stop
          private_methods.waitStop(elWait);
        } catch (ex) {
          private_methods.errMsg("import_data", ex);
          private_methods.waitStop(elWait);
        }
      },

      stop_bubbling: function(event) {
        event.handled = true;
        return false;
      },


      /**
       * sermo_edit
       *   Switch between edit modes for this sermon
       *   And if saving is required, then call the [targeturl] to send a POST of the form data
       *
       */
      sermo_edit: function (el, sType) {
        var sMode = "",
            targetid = "",
            targeturl = "",
            manusurl = "",
            number = "",
            bNew = false,
            data = null,
            frm = null,
            bOkay = true,
            err = "#sermon_err_msg",
            elTd = null,
            parent = "",
            elSermon = "",
            elView = null,
            elEdit = null;

        try {
          // Possibly correct [el]
          if (el !== undefined && "currentTarget" in el) {
            el = el.currentTarget;
          }
          // Check if type is specified
          if (sType === undefined) {
            // Get to the <td> we are in
            elTd = $(el).closest("td");
            if (elTd === undefined || elTd.length === 0) {
              el = this;
              elTd = $(el).closest("td");
            }
            // Check if we need to take the table
            if ($(elTd).hasClass("table")) {
              elTd = $(el).closest("table");
            } else if ($(elTd).hasClass("tabletd")) {
              elTd = $(el).closest("table").closest("td");
            }
          } else {
            // We ourselves are the td
            elTd = el;
          }
          // Get the targeturl and the number
          targeturl = $(elTd).attr("targeturl");
          if (targeturl === undefined) { targeturl = $(el).attr("targeturl"); }
          number = $(elTd).attr("number");
          if (number === undefined) {
            number = $("#sermon_number").attr("number");
          }
          // Get the view and edit values
          elView = $(el).find(".view-mode").first();
          elEdit = $(el).find(".edit-mode").first();
          // Determine the mode we are in
          if (sType !== undefined && sType === "new") {
            // Creating a new one
            sMode = "new";
          } else if ($(el).attr("mode") !== undefined && $(el).attr("mode") !== "") {
            sMode = $(el).attr("mode");
          } else {
            // Check what is opened
            if ($(elView).hasClass("hidden")) {
              // Apparently we are editing, and need to go to VIEW mode (this is the equivalent to Cancel)
              sMode = "view";
            } else {
              // Apparently VIEW is visible, so we are in VIEW mode and need to go to Edit
              sMode = "edit";
            }
          }

          // Act on the mode that we need to SWITCH TO
          switch (sMode) {
            case "view":
            case "cancel":
              // Is this by pressing the 'cancel' button?
              if (el.localName === "a" && $(el).hasClass("btn")) {
                // This is pressing the cancel button
                $(".edit-sermon").addClass("hidden");
                $("#sermon_edit").html("");
                // Show the table data in view mode
                elSermon = "#sermon-number-" + number;
                $(elSermon).find(".view-mode").removeClass("hidden");
                $(elSermon).find(".edit-mode").addClass("hidden");
                //$("#sermon_list").find(".view-mode").removeClass("hidden");
                //$("#sermon_list").find(".edit-mode").addClass("hidden");
              } else {
                // Show the data in view mode
                $(elTd).find(".view-mode").removeClass("hidden");
                $(elTd).find(".edit-mode").addClass("hidden");
              }
              break;
            case "new":
              // (1) Make sure everything in the table is in view-mode
              $("#sermon_list").find(".edit-mode").addClass("hidden");
              $("#sermon_list").find(".view-mode").removeClass("hidden");
              // (2) Request information from the server
              $.get(targeturl, data, function (response) {
                $(".edit-sermon").removeClass("hidden");
                $("#sermon_new").html(response);
                // Determine the number of rows we have
                number = $("#sermon_list").find("tr").length;
                $("#sermon_number").html(" new item (will be #"+number+")");
                $("#sermon_number").attr("number", number);
                $("#sermon_number").attr("new", true);
                // Pass on a message to the user
                // NOTE: this cannot happen, because we are above...
                // $(targetid).html("<i>Please edit sermon " + number + " above and then either Save or Cancel</i>");



                ru.passim.seeker.init_events();
                ru.passim.init_typeahead();
              });
              break;
            case "edit":
              // Go over to edit mode
              // (1) Make sure everything is in view-mode
              $(elTd).closest("table").find(".edit-mode").addClass("hidden");
              $(elTd).closest("table").find(".view-mode").removeClass("hidden");
              // (1) Get the target id
              targetid = $(elTd).find(".edit-mode").first();
              // (2) Show we are loading
              $(elTd).find(".view-mode").addClass("hidden");
              $(elTd).find(".edit-mode").removeClass("hidden");
              $(targetid).html(loc_sWaiting);
              // (2) Request information from the server
              $.get(targeturl, data, function (response) {
                $(".edit-sermon").removeClass("hidden");
                $("#sermon_edit").html(response);
                $("#sermon_number").html(" manuscript item #" + number);
                $("#sermon_number").attr("number", number);
                // Pass on a message to the user
                $(targetid).html("<i>Please edit manuscript item "+number+" above and then either Save or Cancel</i>");
                ru.passim.seeker.init_events();
                ru.passim.init_typeahead();
              });
              break;
            case "delete":
              // Ask for confirmation
              if (!confirm("Do you really want to remove this sermon from the current manuscript?")) {
                // Return from here
                return;
              }
              // (1) Get the form data
              data = $(el).closest("form").serializeArray();
              // (2) Get the manuscript id
              parent = $("#sermon_edit").attr("parent");
              // Add this to the data
              if (parent !== undefined) {
                data.push({ 'name': 'manuscript_id', 'value': parent });
              }
              // (3) Add the action: delete
              data.push({ 'name': 'action', 'value': "delete" });
              // (4) Find out what we need to open later on
              manusurl = $("#sermon_edit").attr("manusurl");
              // (5) Send to the server
              $.post(targeturl, data, function (response) {
                // Action depends on the (JSON!) response
                if (response === undefined || response === null || !("status" in response)) {
                  private_methods.errMsg("No status returned");
                } else {
                  switch (response.status) {
                    case "ready":
                    case "ok":
                    case "error":
                      // If there is an error, indicate this
                      if (response.status === "error") {
                        // Process the error message
                        if ("msg" in response) {
                          r = response['msg'];
                          if (typeof r === "string") {
                            $(err).html("Error: " + response['msg']);
                          } else {
                            lHtml.push("Errors:");
                            for (k in r) {
                              lHtml.push("<br /><b>" + k + "</b>: <code>" + r[k][0] + "</code>");
                            }
                            $(err).html(lHtml.join("\n"));
                          }
                        } else {
                          $(err).html("<code>There is an error</code>");
                        }
                      } else {
                        // There is NO ERROR, all is well...
                        // Deletion has gone well, so renew showing the manuscript
                        window.location.href = manusurl;
                      }
                      break;
                    default:
                      // Something went wrong -- show the page or not?
                      $(err).html("The status returned is unknown: " + response.status);
                      break;
                  }
                }
              });

              ru.passim.seeker.init_events();
              ru.passim.init_typeahead();
              break;
            case "save":
              // Enter into save mode
              // (1) get the target id where the summary should later come
              bNew = ($("#sermon_number").attr("new") !== undefined);
              if (bNew) {
                manusurl = $("#sermon_edit").attr("manusurl");
              } else {
                elSermon = "#sermon-number-" + number;
              }
              // (2) Get the form data
              data = $(el).closest("form").serializeArray();
              // (2) Get the manuscript id
              parent = $("#sermon_edit").attr("parent");
              // Add this to the data
              if (parent !== undefined) {
                data.push({ 'name': 'manuscript_id', 'value': parent });
              }
              // Add the action: edit
              data.push({ 'name': 'action', 'value': "edit" });
              // (3) Send to the server
              $.post(targeturl, data, function (response) {
                var lHtml = [], i, r, k;

                // Action depends on the (JSON!) response
                if (response === undefined || response === null || !("status" in response)) {
                  private_methods.errMsg("No status returned");
                } else {
                  switch (response.status) {
                    case "ready":
                    case "ok":
                    case "error":
                      if ("html" in response) {
                        // If there is an error, indicate this
                        if (response.status === "error") {
                          if ("msg" in response) {
                            r = response['msg'];
                            if (typeof r === "string") {
                              $(err).html("Error: " + response['msg']);
                            } else {
                              lHtml.push("Errors:");
                              for (k in r) {
                                lHtml.push("<br /><b>" + k + "</b>: <code>" + r[k][0] + "</code>");
                              }
                              $(err).html(lHtml.join("\n"));
                            }
                          } else {
                            $(err).html("<code>There is an error</code>");
                          }
                        } else {
                          // There is NO ERROR, all is well...
                          // Check if this is a NEW sermon
                          if (bNew) {
                            // Load and show the whole manuscript
                            window.location.href = manusurl;
                          } else {
                            // Show the HTML in the VIEW-MODE part of elSermon
                            $(elSermon).find(".view-mode").first().html(response['html']);
                            // Make sure the correct part is visible
                            $(elSermon).find(".view-mode").removeClass("hidden");
                            $(elSermon).find(".edit-mode").addClass("hidden");
                            // And now shut down the editable part
                            $(".edit-sermon").addClass("hidden");
                            $("#sermon_edit").html("");
                          }
                        }
                      } else {
                        // Send a message
                        $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                      }
                      break;
                    default:
                      // Something went wrong -- show the page or not?
                      $(err).html("The status returned is unknown: " + response.status);
                      break;
                  }
                }
              });
              break;
          }

        } catch (ex) {
          private_methods.errMsg("sermo_edit", ex);
        }
      },

      /**
       * manu_edit
       *   Switch between edit modes on this <tr>
       *   And if saving is required, then call the [targeturl] to send a POST of the form data
       *
       */
      manu_edit: function (el, sType, oParams) {
        var //el = this,
            sMode = "",
            colspan = "",
            targeturl = "",
            targetid = "",
            afterurl = "",
            targethead = null,
            lHtml = [],
            data = null,
            key = "",
            i=0,
            frm = null,
            bOkay = true,
            bReloading = false,
            manutype = "",
            err = "#little_err_msg",
            elTr = null,
            elView = null,
            elEdit = null;

        try {
          // Possibly correct [el]
          if (el !== undefined && "currentTarget" in el) { el = el.currentTarget; }
          // Get the mode
          if (sType !== undefined && sType !== "") {
            sMode = sType;
          } else {
            sMode = $(el).attr("mode");
          }
          // Get the <tr>
          elTr = $(el).closest("td");
          // Get the manutype
          manutype = $(el).attr("manutype");
          if (manutype === undefined) { manutype = "other"; }

          // Get alternative parameters from [oParams] if this is defined
          if (oParams !== undefined) {
            if ('manutype' in oParams) { manutype = oParams['manutype']; }
          }

          // Check if we need to take the table
          if ($(elTr).hasClass("table")) {
            elTr = $(el).closest("table");
          }
          // Get the view and edit values
          elView = $(el).find(".view-mode").first();
          elEdit = $(el).find(".edit-mode").first();

          // Action depends on the mode
          switch (sMode) {
            case "skip":
              return;
              break;
            case "edit":
              // Make sure all targetid's that need opening are shown
              $(elTr).find(".view-mode:not(.hidden)").each(function () {
                var elTarget = $(this).attr("targetid");
                var targeturl = $(this).attr("targeturl");

                frm = $(el).closest("form");
                data = frm.serializeArray();
                if (elTarget !== undefined && elTarget !== "") {
                  // Do we have a targeturl?
                  if (targeturl !== undefined && targeturl !== "") {
                    // Make a post to the targeturl
                    $.post(targeturl, data, function (response) {
                      // Action depends on the response
                      if (response === undefined || response === null || !("status" in response)) {
                        private_methods.errMsg("No status returned");
                      } else {
                        switch (response.status) {
                          case "ready":
                          case "ok":
                            if ("html" in response) {
                              // Show the HTML in the targetid
                              $("#" + elTarget).html(response['html']);
                            }
                            // In all cases: open the target
                            $("#" + elTarget).removeClass("hidden");
                            // And make sure typeahead works
                            ru.passim.init_typeahead();
                            break;
                        }
                      }
                    });
                  } else {
                    // Just open the target
                    $("#" + elTarget).removeClass("hidden");
                  }
                }
              });
              // Go to edit mode
              $(elTr).find(".view-mode").addClass("hidden");
              $(elTr).find(".edit-mode").removeClass("hidden");
              $(elTr).find(".new-mode").removeClass("hidden");
              // Make sure typeahead works here
              ru.passim.init_typeahead();
              break;
            case "view":
            case "new":
              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");
              targetid = $(el).attr("targetid");
              // If the targetid is specified, we need to get it from there
              if (targetid === undefined || targetid === "") {
                // No targetid specified: just open the target url
                window.location.href = targeturl;
              } else if (loc_bManuSaved) {
                loc_bManuSaved = false;
                // Refresh page
                window.location.href = window.location.href;
              } else {
                switch (manutype) {
                  case "goldlink":
                  case "goldnew":
                  case "newgoldlink":
                    targethead = $("#" + targetid);
                    break;
                  case "goldlinkclose":
                    targethead = $("#" + targetid).closest(".goldlink");
                    $(targethead).addClass("hidden");
                    $(elTr).find(".edit-mode").addClass("hidden");
                    $(elTr).find(".view-mode").removeClass("hidden");
                    return;
                  default:
                    targethead = $("#" + targetid).closest("tr.gold-head");
                    if (targethead !== undefined && targethead.length > 0) {
                      // Targetid is specified: check if we need to close
                      if (!$(targethead).hasClass("hidden")) {
                        // Close it
                        $(targethead).addClass("hidden");
                        return;
                      }
                    } else if ($("#" + targetid).attr("showing") !== undefined) {
                      if ($("#" + targetid).attr("showing") === "true") {
                        $("#" + targetid).attr("showing", "false");
                        $("#" + targetid).html("");
                        return;
                      }
                    }
                    break;
                }

                // There is a targetid specified, so make a GET request for the information and get it here
                data = [];
                // Check if there are any parameters in [oParams]
                if (oParams !== undefined) {
                  for (key in oParams) {
                    data.push({'name': key, 'value': oParams[key]});
                  }
                }

                $.get(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "ready":
                      case "ok":
                      case "error":
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $("#" + targetid).html(response['html']);
                          // Make sure invisible ancestors show up
                          $("#" + targetid).closest(".hidden").removeClass("hidden");
                          // Indicate that we are showing here
                          $("#" + targetid).attr("showing", "true");

                          switch (manutype) {
                            case "goldsermon":
                              // Close any other edit-mode items
                              $(targethead).closest("table").find(".edit-mode").addClass("hidden");
                              // Open this particular edit-mode item
                              $(targethead).removeClass("hidden");
                              break;
                            case "goldlink":
                              $(el).closest("table").find(".edit-mode").addClass("hidden");
                              $(el).closest("table").find(".view-mode").removeClass("hidden");
                              $(elTr).find(".edit-mode").removeClass("hidden");
                              $(elTr).find(".view-mode").addClass("hidden");
                              break;
                            case "goldnew":
                              // Use the new standard approach for *NEW* elements
                              $("#" + targetid).closest(".subform").find(".edit-mode").removeClass("hidden");
                              $("#" + targetid).closest(".subform").find(".view-mode").addClass("hidden");
                              break;
                            default:
                              break;
                          }

                          // Check on specific modes
                          if (sMode === "new") {
                            $("#" + targetid).find(".edit-mode").removeClass("hidden");
                            $("#" + targetid).find(".view-mode").addClass("hidden");
                            // This is 'new', so don't show buttons cancel and delete
                            $("#" + targetid).find("a[mode='cancel'], a[mode='delete']").addClass("hidden");
                            // Since this is new, don't show fields that may not be shown for new
                            $("#" + targetid).find(".edit-notnew").addClass("hidden");
                            $("#" + targetid).find(".edit-new").removeClass("hidden");
                          } else {
                            // Just viewing means we can also delete...
                            // What about CANCEL??
                            // $("#" + targetid).find("a[mode='delete']").addClass("hidden");
                          }

                          // If there is an error, indicate this
                          if (response.status === "error") {
                            if ("msg" in response) {
                              if (typeof response['msg'] === "object") {
                                lHtml = []
                                lHtml.push("Errors:");
                                $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                                $(err).html(lHtml.join("<br />"));
                              } else {
                                $(err).html("Error: " + response['msg']);
                              }
                            } else {
                              $(err).html("<code>There is an error</code>");
                            }
                          }
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  switch (manutype) {
                    case "goldlink":
                    case "goldnew":
                      break;
                    default:
                      // Return to view mode
                      $(elTr).find(".view-mode").removeClass("hidden");
                      $(elTr).find(".edit-mode").addClass("hidden");
                      // Hide waiting symbol
                      $(elTr).find(".waiting").addClass("hidden");
                      break;
                  }
                  // Perform init again
                  ru.passim.init_typeahead();
                  ru.passim.seeker.init_events();
                });

              }
              break;
            case "save":
              // Do we have an afterurl?
              afterurl = $(el).attr("afterurl");

              // Show waiting symbol
              $(elTr).find(".waiting").removeClass("hidden");

              // Make sure we know where the error message should come
              if ($(err).length === 0) { err = $(".err-msg").first();}

              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");
              targetid = $(el).attr("targetid");

              // What if no targetid is specified?
              if (targetid === undefined || targetid === "") {
                // Then we need the parent of our closest enclosing table
                targetid = $(el).closest("form").parent();
              } else {
                targetid = $("#" + targetid);
              }

              // Check
              if (targeturl === undefined) { $(err).html("Save: no <code>targeturl</code> specified"); bOkay = false }
              if (bOkay && targetid === undefined) { $(err).html("Save: no <code>targetid</code> specified"); }

              // Get the form data
              frm = $(el).closest("form");
              if (bOkay && frm === undefined) { $(err).html("<i>There is no <code>form</code> in this page</i>"); }

              // Either POST the request
              if (bOkay) {
                // Get the data into a list of k-v pairs
                data = $(frm).serializeArray();
                // Adapt the value for the [library] based on the [id] 
                // Try to save the form data: send a POST
                $.post(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "error":
                        // Indicate there is an error
                        bOkay = false;
                        // Show the error in an appropriate place
                        if ("msg" in response) {
                          if (typeof response['msg'] === "object") {
                            lHtml = [];
                            lHtml.push("Errors:");
                            $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                            $(err).html(lHtml.join("<br />"));
                          } else {
                            $(err).html("Error: " + response['msg']);
                          }
                        } else if ("errors" in response) {
                          lHtml = [];
                          lHtml.push("<h4>Errors</h4>");
                          for (i = 0; i < response['errors'].length; i++) {
                            $.each(response['errors'][i], function (key, value) {
                              lHtml.push("<b>"+ key + "</b>: </i>" + value + "</i>");
                            });
                          }
                          $(err).html(lHtml.join("<br />"));
                        } else if ("error_list" in response) {
                          lHtml = [];
                          lHtml.push("Errors:");
                          $.each(response['error_list'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("<code>There is an error</code>");
                        }
                        break;
                      case "ready":
                      case "ok":
                        // First check for afterurl
                        if (afterurl !== undefined && afterurl !== "") {
                          // Make sure we go to the afterurl
                          window.location = afterurl;
                        }
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $(targetid).html(response['html']);
                          // Signal globally that something has been saved
                          loc_bManuSaved = true;
                          // If an 'afternewurl' is specified, go there
                          if ('afternewurl' in response && response['afternewurl'] !== "") {
                            window.location = response['afternewurl'];
                            bReloading = true;
                          } else {
                            // nothing else yet
                          }
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  if (!bReloading && bOkay) {
                    // Return to view mode
                    $(elTr).find(".view-mode").removeClass("hidden");
                    $(elTr).find(".edit-mode").addClass("hidden");
                    // Hide waiting symbol
                    $(elTr).find(".waiting").addClass("hidden");
                    // Perform init again
                    ru.passim.seeker.init_events();
                  }
                });
              } else {
                // Or else stop waiting - with error message above
                $(elTr).find(".waiting").addClass("hidden");
              }

              break;
            case "cancel":
              // Make sure all targetid's that need closing are hidden
              $(elTr).find(".edit-mode:not(.hidden)").each(function () {
                var elTarget = $(this).attr("targetid");
                if (elTarget !== undefined && elTarget !== "") {
                  $("#" + elTarget).addClass("hidden");
                }
              });
              // Go to view mode without saving
              $(elTr).find(".view-mode").removeClass("hidden");
              $(elTr).find(".edit-mode").addClass("hidden");
              $(elTr).find(".new-mode").addClass("hidden");
              break;
            case "delete":
              // Do we have an afterurl?
              afterurl = $(el).attr("afterurl");

              // Check if we are under a delete-confirm
              if (!$(el).closest("div").hasClass("delete-confirm")) {
                // Ask for confirmation
                // NOTE: we cannot be more specific than "item", since this can be manuscript or sermongold
                if (!confirm("Do you really want to remove this item?")) {
                  // Return from here
                  return;
                }
              }
              // Show waiting symbol
              $(elTr).find(".waiting").removeClass("hidden");

              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");

              // Determine targetid from own
              targetid = $(el).closest(".gold-head");
              targethead = $(targetid).prev();

              // Check
              if (targeturl === undefined) { $(err).html("Save: no <code>targeturl</code> specified"); bOkay = false }

              // Get the form data
              frm = $(el).closest("form");
              if (bOkay && frm === undefined) { $(err).html("<i>There is no <code>form</code> in this page</i>"); }
              // Either POST the request
              if (bOkay) {
                // Get the data into a list of k-v pairs
                data = $(frm).serializeArray();
                // Add the delete mode
                data.push({ name: "action", value: "delete" });

                // Try to delete: send a POST
                $.post(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "ready":
                      case "ok":
                        // Do we have afterdelurl afterurl?
                        // If an 'afternewurl' is specified, go there
                        if ('afterdelurl' in response && response['afterdelurl'] !== "") {
                          window.location = response['afterdelurl'];
                        } else if (afterurl === undefined || afterurl === "") {
                          // Delete visually
                          $(targetid).remove();
                          $(targethead).remove();
                        } else {
                          // Make sure we go to the afterurl
                          window.location = afterurl;
                        }
                        break;
                      case "error":
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $(err).html(response['html']);
                          // If there is an error, indicate this
                          if (response.status === "error") {
                            if ("msg" in response) {
                              if (typeof response['msg'] === "object") {
                                lHtml = []
                                lHtml.push("Errors:");
                                $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                                $(err).html(lHtml.join("<br />"));
                              } else {
                                $(err).html("Error: " + response['msg']);
                              }
                            } else {
                              $(err).html("<code>There is an error</code>");
                            }
                          } 
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  // Return to view mode
                  $(elTr).find(".view-mode").removeClass("hidden");
                  $(elTr).find(".edit-mode").addClass("hidden");
                  // Hide waiting symbol
                  $(elTr).find(".waiting").addClass("hidden");
                  // Perform init again
                  ru.passim.seeker.init_events();
                });
              } else {
                // Or else stop waiting - with error message above
                $(elTr).find(".waiting").addClass("hidden");
              }


              break;
          }
        } catch (ex) {
          private_methods.errMsg("manu_edit", ex);
        }
      },


      /**
       * goto_url
       *   Go to the indicated target URL
       *
       */
      goto_url: function (target) {
        try {
          location.href = target;
        } catch (ex) {
          private_methods.errMsg("goto_url", ex);
        }
      },

      /**
       * gold_row_edit
       *   Switch everything in the current <tr> according to the mode
       *
       */
      gold_row_edit: function (el, mode, option) {
        var elTr = null,
            elDiv = null;

        try {
          // Get to the <tr>
          elTr = $(el).closest("tr");
          // Action depends on mode
          switch (mode) {
            case "edit":
              // Start editing
              $(elTr).find(".edit-mode").removeClass("hidden");
              $(elTr).find(".view-mode").addClass("hidden");
              $(el).closest("td").addClass("hightlighted");
              if (option !== undefined && option === "select2") {
                elDiv = $(el).closest("div[id]");

                ru.passim.seeker.init_select2($(elDiv).attr("id"));
              }
              break;
            case "view":
              $(el).closest("td").removeClass("hightlighted");
              // Save edit results, post the results and if all is well, show the view

              // If everything went well show the view mode
              $(elTr).find(".edit-mode").addClass("hidden");
              $(elTr).find(".view-mode").removeClass("hidden");
              break;
          }
        } catch (ex) {
          private_methods.errMsg("gold_row_edit", ex);
        }
      },

      /**
       * base_sermon
       *   Base the sermon on the gold-sermon identified by sClass
       *
       */
      base_sermon: function (el, sClass) {
        var frm = null,
            url = "",
            data = null,
            goldid = "";

        try {
          // Get to the form I'm in
          frm = $(el).closest("form");
          // Get the initial URL
          url = $(el).attr("targeturl");
          // Does it have a number for the gold sermon?
          if (url.indexOf("goldid") < 0 && !url.match(/\/\d+\/$/i)) {
            // Find the gold-sermon ID
            goldid = $(frm).find("." + sClass + " input").first().val();
            // Get the values of this gold sermonid
            url = url + "?goldid=" + goldid;
          }
          $.get(url, null, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ok":
                  // Process the results
                  data = response['data'];
                  $("#id_sermo-incipit").val(data['incipit']);
                  $("#id_sermo-explicit").val(data['explicit']);
                  $("#id_sermo-author").val(data['author']);
                  $("#id_sermo-authorname").val(data['authorname']);
                  // Set editing mode
                  $(".sermon-details a[mode=edit]").click();
                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $(targetid).html(response.msg);
                  } else {
                    $(targetid).html("An error has occurred (passim.seeker base_sermon)");
                  }
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("base_sermon", ex);
        }
      },

      /**
       * delete_confirm
       *   Open the next <tr> to get delete confirmation (or not)
       *
       */
      delete_confirm: function (el, bNeedConfirm) {
        var elDiv = null;

        try {
          if (bNeedConfirm === undefined) { bNeedConfirm = true; }
          // Action depends on the need for confirmation
          if (bNeedConfirm) {
            // Find the [.delete-row] to be shown
            elDiv = $(el).closest("tr").find(".delete-confirm").first();
            if (elDiv.length === 0) {
              // Try goint to the next <tr>
              elDiv = $(el).closest("tr").next("tr.delete-confirm");
            }
            $(elDiv).removeClass("hidden");
          } else {

          }
        } catch (ex) {
          private_methods.errMsg("delete_confirm", ex);
        }
      },

      /**
       * delete_cancel
       *   Hide this <tr> and cancel the delete
       *
       */
      delete_cancel: function (el) {
        try {
          $(el).closest("div.delete-confirm").addClass("hidden");
        } catch (ex) {
          private_methods.errMsg("delete_cancel", ex);
        }
      },

      /**
       * elevate_confirm
       *   Open the next <tr> to get delete confirmation (or not)
       *
       */
      elevate_confirm: function (el, bNeedConfirm) {
        var elDiv = null;

        try {
          if (bNeedConfirm === undefined) { bNeedConfirm = true; }
          // Action depends on the need for confirmation
          if (bNeedConfirm) {
            // Find the [.elevate-row] to be shown
            elDiv = $(el).closest("tr").find(".elevate-confirm").first();
            if (elDiv.length === 0) {
              // Try goint to the next <tr>
              elDiv = $(el).closest("tr").next("tr.elevate-confirm");
            }
            $(elDiv).removeClass("hidden");
          } else {

          }
        } catch (ex) {
          private_methods.errMsg("elevate_confirm", ex);
        }
      },

      /**
       * elevate_cancel
       *   Hide this <tr> and cancel the delete
       *
       */
      elevate_cancel: function (el) {
        try {
          $(el).closest("div.elevate-confirm").addClass("hidden");
        } catch (ex) {
          private_methods.errMsg("elevate_cancel", ex);
        }
      },

      /**
       * formset_setdel
       *   Set the delete checkbox of me
       *
       */
      formset_setdel: function (elStart) {

        try {
          // Set the delete value of the checkbox
          $(elStart).closest("td").find("input[type=checkbox]").first().prop("checked", true);
        } catch (ex) {
          private_methods.errMsg("formset_setdel", ex);
        }
      },

      /**
       * formset_update
       *   Send an Ajax POST request and process the response in a standard way
       *
       */
      formset_update: function (elStart, sAction) {
        var targetid = "",
            err = "#error_location",
            errdiv = null,
            waitclass = ".formset-wait",
            elWaitRow = null,
            data = [],
            lHtml = [],
            i = 0,
            frm = null,
            targeturl = "";

        try {
          // Get the correct error div
          errdiv = $(elStart).closest("form").find(err).first();
          if (errdiv === undefined || errdiv === null) {
            errdiv = $(err);
          }

          // Get attributes
          targetid = $(elStart).attr("targetid");
          targeturl = $(elStart).attr("targeturl");

          // Possibly set delete flag
          if (sAction !== undefined && sAction !== "") {
            switch (sAction) {
              case "delete":
                // Set the delete value of the checkbox
                $(elStart).closest("td").find("input[type=checkbox]").first().prop("checked", true);
                break;
              case "wait":
                // Set a waiting thing at the targetid
                $("#" + targetid).html(loc_sWaiting);
                // Make sure the caller is inactivated
                $(elStart).addClass("hidden");
                break;
            }
          }

          // Check if there is a waiting row
          elWaitRow = $(elStart).closest("table").find(waitclass);
          if (elWaitRow.length > 0) { $(elWaitRow).removeClass('hidden');}

          // Gather the data
          frm = $(elStart).closest("form");
          data = $(frm).serializeArray();
          data = jQuery.grep(data, function (item) {
            return (item['value'].indexOf("__counter__") < 0 && item['value'].indexOf("__prefix__") < 0);
          });
          $.post(targeturl, data, function (response) {
            // Show we have a response
            if (elWaitRow.length > 0) { $(elWaitRow).addClass('hidden'); }

            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                case "error":
                  if ("html" in response) {
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(errdiv).html(lHtml.join("<br />"));
                        } else {
                          $(errdiv).html("Error: " + response['msg']);
                        }
                      } else if ('error_list' in response) {
                        lHtml = []
                        lHtml.push("Errors:");
                        for (i = 0; i < response['error_list'].length; i++) {
                          lHtml.push(response['error_list'][i]);
                        }
                        $(errdiv).html(lHtml.join("<br />"));
                      } else {
                        $(errdiv).html("<code>There is an error</code>");
                      }
                      $(errdiv).removeClass("hidden");
                    } else {
                      // Show the HTML in the targetid
                      $("#" + targetid).html(response['html']);
                      // Action...
                      if (sAction !== undefined && sAction !== "") {
                        switch (sAction) {
                          case "wait":
                            $(elStart.removeClass("hidden"));
                            break;
                        }
                      }
                      // Check for other specific matters
                      switch (targetid) {
                        case "sermongold_eqset":
                          // We need to update 'sermongold_linkset'
                          ru.passim.seeker.do_get("sermongold_linkset");
                          break;
                        case "sermon_linkset":
                          // We need to update 'sermongold_ediset'
                          ru.passim.seeker.do_get("sermondescr_ediset");
                          break;
                      }
                    }
                    // But make sure events are back on again
                    ru.passim.seeker.init_events();
                  } else {
                    // Send a message
                    $(errdiv).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(errdiv).html("The status returned is unknown: " + response.status);
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("formset_update", ex);
        }
      },

      /**
       * tabular_deleterow
       *   Delete one row from a tabular inline
       *
       */
      tabular_deleterow: function () {
        var sId = "",
            elDiv = null,
            elRow = null,
            elPrev = null,
            elDel = null,   // The delete inbox
            sPrefix = "",
            elForms = "",
            counter = $(this).attr("counter"),
            deleteurl = "",
            data = [],
            frm = null,
            bCounter = false,
            bHideOnDelete = false,
            iForms = 0,
            prefix = "simplerel",
            use_prev_row = false,   // Delete the previous row instead of the current one
            bValidated = false;

        try {
          // Get the prefix, if possible
          sPrefix = $(this).attr("extra");
          bCounter = (typeof counter !== typeof undefined && counter !== false && counter !== "");
          elForms = "#id_" + sPrefix + "-TOTAL_FORMS"
          // Find out just where we are
          elDiv = $(this).closest("div[id]")
          sId = $(elDiv).attr("id");
          // Find out how many forms there are right now
          iForms = $(elForms).val();
          frm = $(this).closest("form");
          // The validation action depends on this id
          switch (sId) {
            // gold
            case "glink_formset":
            case "gedi_formset":
            case "gftxt_formset":
            case "gsign_formset":
            case "gkw_formset":
            case "gcol_formset":
            // super
            case "scol_formset":
            case "ssglink_formset":
            // sermo 
            case "stog_formset":
            case "sdsignformset":
            case "sdcol_formset":
            case "sdkw_formset":
            // manu
            case "mprov_formset":
            case "mdr_formset":
            case "mkw_formset":
            case "mcol_formset":
            case "manu_search":
              //// Indicate that deep evaluation is needed
              //if (!confirm("Do you really want to remove this gold sermon? (All links to and from this gold sermon will also be removed)")) {
              //  // Return from here
              //  return;
              //}
              use_prev_row = false;
              bValidated = true;
              break;
          }
          // Continue with deletion only if validated
          if (bValidated) {
            // Get the deleteurl (if existing)
            deleteurl = $(this).attr("targeturl");
            // Get to the row
            if (use_prev_row) {
              // Delete both the current and the previous row
              elRow = $(this).closest("tr");
              elPrev = $(elRow).prev();
              $(elRow).remove();
              $(elPrev).remove();
            } else {
              // Only delete the current row
              elRow = $(this).closest("tr");
              // Do we need to hide or delete?
              if ($(elRow).hasClass("hide-on-delete")) {
                bHideOnDelete = true;
                $(elRow).addClass("hidden");
              } else {
                $(elRow).remove();
              }
            }

            // Further action depends on whether the row just needs to be hidden
            if (bHideOnDelete) {
              // Row has been hidden: now find and set the DELETE checkbox
              elDel = $(elRow).find("input:checkbox[name$='DELETE']");
              if (elDel !== null) {
                $(elDel).prop("checked", true);
              }
            } else {
              // Decrease the amount of forms
              iForms -= 1;
              $(elForms).val(iForms);

              // Re-do the numbering of the forms that are shown
              $(elDiv).find(".form-row").not(".empty-form").each(function (idx, elThisRow) {
                var iCounter = 0, sRowId = "", arRowId = [];

                iCounter = idx + 1;
                // Adapt the ID attribute -- if it EXISTS
                sRowId = $(elThisRow).attr("id");
                if (sRowId !== undefined) {
                  arRowId = sRowId.split("-");
                  arRowId[1] = idx;
                  sRowId = arRowId.join("-");
                  $(elThisRow).attr("id", sRowId);
                }

                if (bCounter) {
                  // Adjust the number in the FIRST <td>
                  $(elThisRow).find("td").first().html(iCounter.toString());
                }

                // Adjust the numbering of the INPUT and SELECT in this row
                $(elThisRow).find("input, select").each(function (j, elInput) {
                  // Adapt the name of this input
                  var sName = $(elInput).attr("name");
                  if (sName !== undefined) {
                    var arName = sName.split("-");
                    arName[1] = idx;
                    sName = arName.join("-");
                    $(elInput).attr("name", sName);
                    $(elInput).attr("id", "id_" + sName);
                  }
                });
              });
            }

            // The validation action depends on this id (or on the prefix)
            switch (sId) {
              case "search_mode_simple":
                // Update -- NOTE: THIS IS A LEFT-OVER FROM CESAR
                ru.passim.seeker.simple_update();
                break;
              case "ssglink_formset":
                if (deleteurl !== undefined &&  deleteurl !== "") {
                  // prepare data
                  data = $(frm).serializeArray();
                  data.push({ 'name': 'action', 'value': 'delete' });
                  $.post(deleteurl, data, function (response) {
                    // Action depends on the response
                    if (response === undefined || response === null || !("status" in response)) {
                      private_methods.errMsg("No status returned");
                    } else {
                      switch (response.status) {
                        case "ready":
                        case "ok":
                          // Refresh the current page
                          window.location = window.location;
                          break;
                        case "error":
                          // Show the error
                          if ('msg' in response) {
                            $(targetid).html(response.msg);
                          } else {
                            $(targetid).html("An error has occurred (passim.seeker tabular_deleterow)");
                          }
                          break;
                      }
                    }
                  });
                }
                break;
            }
          }

        } catch (ex) {
          private_methods.errMsg("tabular_deleterow", ex);
        }
      },

      /**
       * tabular_addrow
       *   Add one row into a tabular inline
       *
       */
      tabular_addrow: function (elStart, options) {
        // NOTE: see the definition of lAddTableRow above
        var arTdef = lAddTableRow,
            oTdef = {},
            rowNew = null,
            elTable = null,
            select2_options = {},
            iNum = 0,     // Number of <tr class=form-row> (excluding the empty form)
            sId = "",
            bSelect2 = false,
            i;

        try {
          // Find out just where we are
          if (elStart === undefined || elStart === null || $(elStart).closest("div").length === 0)
            elStart = $(this);
          sId = $(elStart).closest("div[id]").attr("id");
          // Process options
          if (options !== undefined) {
            for (var prop in options) {
              switch (prop) {
                case "select2": bSelect2 = options[prop]; break;
              }
            }
          } else {
            options = $(elStart).attr("options");
            if (options !== undefined && options === "select2") {
              bSelect2 = true;
            }
          }
          // Walk all tables
          for (i = 0; i < arTdef.length; i++) {
            // Get the definition
            oTdef = arTdef[i];
            if (sId === oTdef.table || sId.indexOf(oTdef.table) >= 0) {
              // Go to the <tbody> and find the last form-row
              elTable = $(elStart).closest("tbody").children("tr.form-row.empty-form")

              if ("select2_options" in oTdef) {
                select2_options = oTdef.select2_options;
              }

              // Perform the cloneMore function to this <tr>
              rowNew = ru.passim.seeker.cloneMore(elTable, oTdef.prefix, oTdef.counter);
              // Call the event initialisation again
              if (oTdef.events !== null) {
                oTdef.events();
              }
              // Possible Select2 follow-up
              if (bSelect2) {
                // Remove previous .select2
                $(rowNew).find(".select2").remove();
                // Execute djangoSelect2()
                $(rowNew).find(".django-select2").djangoSelect2(select2_options);
              }
              // Any follow-up activity
              if ('follow' in oTdef && oTdef['follow'] !== null) {
                oTdef.follow(rowNew);
              }
              // We are done...
              break;
            }
          }
        } catch (ex) {
          private_methods.errMsg("tabular_addrow", ex);
        }
      },

      /**
       *  cloneMore
       *      Add a form to the formset
       *      selector = the element that should be duplicated
       *      type     = the formset type
       *      number   = boolean indicating that re-numbering on the first <td> must be done
       *
       */
      cloneMore: function (selector, type, number) {
        var elTotalForms = null,
            total = 0;

        try {
          // Clone the element in [selector]
          var newElement = $(selector).clone(true);
          // Find the total number of [type] elements
          elTotalForms = $('#id_' + type + '-TOTAL_FORMS').first();
          // Determine the total of already available forms
          if (elTotalForms === null || elTotalForms.length ===0) {
            // There is no TOTAL_FORMS for this type, so calculate myself
          } else {
            // Just copy the TOTAL_FORMS value
            total = parseInt($(elTotalForms).val(), 10);
          }

          // Find each <input> element
          newElement.find(':input').each(function (idx, el) {
            var name = "",
                id = "",
                val = "",
                td = null;

            if ($(el).attr("name") !== undefined) {
              // Get the name of this element, adapting it on the fly
              name = $(el).attr("name").replace("__prefix__", total.toString());
              // Produce a new id for this element
              id = $(el).attr("id").replace("__prefix__", total.toString());
              // Adapt this element's name and id, unchecking it
              $(el).attr({ 'name': name, 'id': id }).val('').removeAttr('checked');
              // Possibly set a default value
              td = $(el).parent('td');
              if (td.length === 0) {
                td = $(el).parent("div").parent("td");
              }
              if (td.length === 1) {
                val = $(td).attr("defaultvalue");
                if (val !== undefined && val !== "") {
                  $(el).val(val);
                }
              }
            }
          });
          newElement.find('select').each(function (idx, el) {
            var td = null;

            if ($(el).attr("name") !== undefined) {
              td = $(el).parent('td');
              if (td.length === 0) { td = $(el).parent("div").parent("td"); }
              if (td.length === 0 || (td.length === 1 && $(td).attr("defaultvalue") === undefined)) {
                // Get the name of this element, adapting it on the fly
                var name = $(el).attr("name").replace("__prefix__", total.toString());
                // Produce a new id for this element
                var id = $(el).attr("id").replace("__prefix__", total.toString());
                // Adapt this element's name and id, unchecking it
                $(el).attr({ 'name': name, 'id': id }).val('').removeAttr('checked');
              }
            }
          });

          // Find each <label> under newElement
          newElement.find('label').each(function (idx, el) {
            if ($(el).attr("for") !== undefined) {
              // Adapt the 'for' attribute
              var newFor = $(el).attr("for").replace("__prefix__", total.toString());
              $(el).attr('for', newFor);
            }
          });

          // Look at the inner text of <td>
          newElement.find('td').each(function (idx, el) {
            var elInsideTd = $(el).find("td");
            var elText = $(el).children().first();
            if (elInsideTd.length === 0 && elText !== undefined) {
              var sHtml = $(elText).html();
              if (sHtml !== undefined && sHtml !== "") {
                sHtml = sHtml.replace("__counter__", (total+1).toString());
                $(elText).html(sHtml);
              }
              // $(elText).html($(elText).html().replace("__counter__", total.toString()));
            }
          });
          // Look at the attributes of <a> and of <input>
          newElement.find('a, input').each(function (idx, el) {
            // Iterate over all attributes
            var elA = el;
            $.each(elA.attributes, function (i, attrib) {
              var attrText = $(elA).attr(attrib.name).replace("__counter__", total.toString());
              // EK (20/feb): $(this).attr(attrib.name, attrText);
              $(elA).attr(attrib.name, attrText);
            });
          });


          // Adapt the total number of forms in this formset
          total++;
          $('#id_' + type + '-TOTAL_FORMS').val(total);

          // Adaptations on the new <tr> itself
          newElement.attr("id", "arguments-" + (total - 1).toString());
          newElement.attr("class", "form-row row" + total.toString());

          // Insert the new element before the selector = empty-form
          $(selector).before(newElement);

          // Should we re-number?
          if (number !== undefined && number) {
            // Walk all <tr> elements of the table
            var iRow = 1;
            $(selector).closest("tbody").children("tr.form-row").not(".empty-form").each(function (idx, el) {
              var elFirstCell = $(el).find("td").not(".hidden").first();
              $(elFirstCell).html(iRow);
              iRow += 1;
            });
          }

          // Return the new <tr> 
          return newElement;

        } catch (ex) {
          private_methods.errMsg("cloneMore", ex);
          return null;
        }
      },

      /**
       * toggle_click
       *   Action when user clicks an element that requires toggling a target
       *
       */
      toggle_click: function (elThis, class_to_close) {
        var elGroup = null,
            elTarget = null,
            sStatus = "";

        try {
          // Get the target to be opened
          elTarget = $(elThis).attr("targetid");
          // Sanity check
          if (elTarget !== null) {
            // Show it if needed
            if ($("#" + elTarget).hasClass("hidden")) {
              $("#" + elTarget).removeClass("hidden");
            } else {
              $("#" + elTarget).addClass("hidden");
              // Check if there is an additional class to close
              if (class_to_close !== undefined && class_to_close !== "") {
                $("." + class_to_close).addClass("hidden");
              }
            }
          }
        } catch (ex) {
          private_methods.errMsg("toggle_click", ex);
        }
      },

    };
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

